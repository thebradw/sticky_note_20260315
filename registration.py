# registration.py - T4.0 geometric registration for multi-photo stitching
#
# Pure geometry module: no Anthropic calls, no Flask, no session state.
# Computes a SIFT/RANSAC homography that maps detail-photo pixel coordinates
# into overview pixel coordinates, so detail note bboxes can be transformed
# deterministically and matched by nearest-neighbor distance.
#
# Coordinate space rule (critical): all bboxes live in the Vision coordinate
# space — the exact per-image dimensions Claude's server-side pipeline
# resizes to, computed by vision_resized_size() in image_analyzer.py (edge
# limit AND visual-token limit; aspect-ratio dependent, NOT a fixed
# constant). encode_image() submits images at exactly those dimensions and
# load_vision_image() below loads through the same helper, so every image
# has exactly one coordinate space. Never introduce a second coordinate
# bookkeeping system.

import cv2
import numpy as np
from PIL import Image

# Internal SIFT working resolution. Feature detection and the RANSAC
# acceptance gates run at this resolution — the one the brief's constants
# (REG_MIN_INLIERS, REG_MIN_INLIER_RATIO) were calibrated at. The resulting
# homography is composed into each image's Vision space before being
# returned, so callers only ever see Vision-space coordinates.
REG_DETECT_MAX_DIM = 2400

# Config constants — validated on repo fixtures 2026-07-02
# (child1/2/3 close-ups register to 24/58/82% of leftright_wholewall.jpeg
# width; a change that moves those anchors by more than ±10% is wrong).
REG_MAX_FEATURES          = 8000
REG_LOWE_RATIO            = 0.75
REG_RANSAC_REPROJ         = 5.0
REG_MIN_INLIERS           = 30     # child3 (weakest fixture) scored 53
REG_MIN_INLIER_RATIO      = 0.20
REG_MATCH_MAX_DIST_FACTOR = 0.75   # x median overview note width


def _load_vision_pil(image_path):
    """Load an image as grayscale PIL in the Vision coordinate space.

    Applies the SAME resize as StickyNoteAnalyzer.encode_image(): the exact
    per-image dimensions Claude's server-side pipeline would resize to
    (vision_resized_size — edge + visual-token limits).
    """
    # Lazy import: image_analyzer imports this module at top level, so a
    # top-level import here would be circular. By the time this function
    # runs, image_analyzer is fully importable.
    from image_analyzer import vision_resized_size

    with Image.open(image_path) as img:
        target = vision_resized_size(*img.size)
        if target != img.size:
            img = img.resize(target, Image.Resampling.LANCZOS)
        return img.convert('L')


def load_vision_image(image_path):
    """Load an image in grayscale in the Vision coordinate space.

    Returns a 2D uint8 numpy array in the same coordinate space as the
    bboxes Claude Vision reports (submitted pixels == model-seen pixels).
    """
    return np.asarray(_load_vision_pil(image_path))


def _detection_copy(vision_pil):
    """Downscale a Vision-space PIL image to the SIFT working resolution.

    Returns (gray_array, scale) where scale = detection_width / vision_width,
    i.e. the factor that maps Vision-space coordinates INTO detection space.
    Computed per image from actual post-resize sizes (Vision space itself is
    per-image, so there is no fixed ratio; images already at or below the
    detection resolution pass through with scale 1.0).
    """
    det = vision_pil.copy()
    if max(det.size) > REG_DETECT_MAX_DIM:
        det.thumbnail((REG_DETECT_MAX_DIM, REG_DETECT_MAX_DIM),
                      Image.Resampling.LANCZOS)
    scale = det.size[0] / vision_pil.size[0]
    return np.asarray(det), scale


def _projected_corners(H, width, height):
    """Project the four corners of a width x height image through H.

    Returns a 4x2 float array ordered TL, TR, BR, BL in destination space.
    """
    corners = np.float32([
        [0, 0], [width, 0], [width, height], [0, height]
    ]).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(corners, H).reshape(-1, 2)


def _is_convex_positive_quad(quad):
    """True if the 4-point polygon is convex with positive (non-zero) area."""
    contour = quad.reshape(-1, 1, 2).astype(np.float32)
    area = cv2.contourArea(contour)
    if area <= 0:
        return False
    return bool(cv2.isContourConvex(contour))


def register_detail_to_overview(overview_path, detail_path):
    """Compute the homography mapping detail-photo pixels into overview pixels.

    DETECTION RESOLUTION vs. BBOX COORDINATE SPACE — deliberately decoupled:
    SIFT detection, Lowe-ratio matching, RANSAC, and the inlier acceptance
    gates all run at up to REG_DETECT_MAX_DIM (2400px), the resolution the
    brief's gate constants were calibrated at (at higher working resolutions
    the ratio-test match pool grows and inlier ratios drop below the
    calibrated gates even for correct homographies). The RANSAC result
    H_detect is then composed into each image's Vision bbox space using
    per-image scale factors measured from actual post-resize dimensions:

        H_vision = inv(S_overview) @ H_detect @ S_detail
        (S = diag(scale, scale, 1), scale = detection_dim / vision_dim)

    Only the composed Vision-space homography (and quantities derived from
    it) leave this function — nothing downstream ever sees or touches the
    detection space, so note bboxes still live in exactly one coordinate
    system: the per-image dimensions Claude actually sees, computed by
    vision_resized_size() (NOT a fixed constant — edge and visual-token
    limits bind differently per aspect ratio).

    Pipeline: load both images grayscale through the Vision resize helper ->
    downscale working copies to REG_DETECT_MAX_DIM ->
    SIFT (nfeatures=REG_MAX_FEATURES) -> BFMatcher(NORM_L2) knnMatch(k=2) ->
    Lowe ratio test at REG_LOWE_RATIO -> cv2.findHomography(RANSAC) ->
    compose into Vision space.

    Acceptance gates (all must pass, else status='failed'):
      1. inliers >= REG_MIN_INLIERS            (evaluated at 2400px)
      2. inlier_ratio >= REG_MIN_INLIER_RATIO  (evaluated at 2400px)
      3. projected detail corners form a convex quadrilateral with positive area
      4. projected region center lies within overview image bounds

    Returns:
        {
            'status': 'ok' | 'failed',
            'homography': 3x3 np.ndarray or None,
            'inliers': int,
            'inlier_ratio': float,
            'projected_region': [[x, y] x4] or None,  # detail corners in overview space
            'reason': str  # populated when status == 'failed'
        }
    """
    result = {
        'status': 'failed',
        'homography': None,
        'inliers': 0,
        'inlier_ratio': 0.0,
        'projected_region': None,
        'reason': ''
    }

    try:
        overview_pil = _load_vision_pil(overview_path)
        detail_pil = _load_vision_pil(detail_path)
    except Exception as e:
        result['reason'] = f'image load failed: {e}'
        return result

    # SIFT works on 2400px copies; scales map Vision space -> detection space
    overview_img, scale_overview = _detection_copy(overview_pil)
    detail_img, scale_detail = _detection_copy(detail_pil)

    sift = cv2.SIFT_create(nfeatures=REG_MAX_FEATURES)
    kp_detail, des_detail = sift.detectAndCompute(detail_img, None)
    kp_overview, des_overview = sift.detectAndCompute(overview_img, None)

    if des_detail is None or des_overview is None:
        result['reason'] = 'no SIFT features detected in one or both images'
        return result
    if len(kp_detail) < 4 or len(kp_overview) < 4:
        result['reason'] = 'too few SIFT features for homography'
        return result

    matcher = cv2.BFMatcher(cv2.NORM_L2)
    knn_matches = matcher.knnMatch(des_detail, des_overview, k=2)

    good_matches = []
    for pair in knn_matches:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < REG_LOWE_RATIO * n.distance:
            good_matches.append(m)

    if len(good_matches) < 4:
        result['reason'] = (
            f'only {len(good_matches)} ratio-test matches (need >= 4)')
        return result

    src_pts = np.float32(
        [kp_detail[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32(
        [kp_overview[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

    H_detect, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC,
                                        REG_RANSAC_REPROJ)
    if H_detect is None or mask is None:
        result['reason'] = 'findHomography failed to converge'
        return result

    inliers = int(mask.sum())
    inlier_ratio = inliers / len(good_matches)
    result['inliers'] = inliers
    result['inlier_ratio'] = round(inlier_ratio, 4)

    # Compose detection-space homography into Vision bbox space:
    # H_vision = inv(S_overview) @ H_detect @ S_detail
    s_detail = np.diag([scale_detail, scale_detail, 1.0])
    s_overview_inv = np.diag([1.0 / scale_overview, 1.0 / scale_overview, 1.0])
    H = s_overview_inv @ H_detect @ s_detail

    # Gate 1: absolute inlier count
    if inliers < REG_MIN_INLIERS:
        result['reason'] = (
            f'inliers {inliers} < REG_MIN_INLIERS {REG_MIN_INLIERS}')
        return result

    # Gate 2: inlier ratio
    if inlier_ratio < REG_MIN_INLIER_RATIO:
        result['reason'] = (
            f'inlier ratio {inlier_ratio:.2f} < '
            f'REG_MIN_INLIER_RATIO {REG_MIN_INLIER_RATIO}')
        return result

    # Gates 3 and 4 evaluate in Vision space with the composed homography
    detail_w, detail_h = detail_pil.size
    quad = _projected_corners(H, detail_w, detail_h)

    # Gate 3: projected corners form a convex quad with positive area
    if not _is_convex_positive_quad(quad):
        result['reason'] = 'projected detail region is degenerate (non-convex)'
        return result

    # Gate 4: projected region center within overview bounds
    center_x, center_y = quad.mean(axis=0)
    overview_w, overview_h = overview_pil.size
    if not (0 <= center_x <= overview_w and 0 <= center_y <= overview_h):
        result['reason'] = (
            f'projected center ({center_x:.0f}, {center_y:.0f}) outside '
            f'overview bounds ({overview_w} x {overview_h})')
        return result

    result['status'] = 'ok'
    result['homography'] = H
    result['projected_region'] = [[float(x), float(y)] for x, y in quad]
    result['reason'] = ''
    return result


def transform_bbox(bbox, H):
    """Transform a [x1, y1, x2, y2] bbox through homography H.

    Projects all 4 corners and returns the axis-aligned
    [min_x, min_y, max_x, max_y] in overview space.
    """
    x1, y1, x2, y2 = bbox
    corners = np.float32([
        [x1, y1], [x2, y1], [x2, y2], [x1, y2]
    ]).reshape(-1, 1, 2)
    projected = cv2.perspectiveTransform(corners, np.asarray(H, dtype=np.float64)).reshape(-1, 2)
    return [
        float(projected[:, 0].min()),
        float(projected[:, 1].min()),
        float(projected[:, 0].max()),
        float(projected[:, 1].max()),
    ]
