# Troubleshooting: PDF Generation

## Quick Diagnosis

If the "Generate PDF" button doesn't work, work through these checks in order.

### 1. Flask App Not Restarted
**Most Common Cause**

The Flask development server needs to be restarted to load any updated code.

**Solution:**
```bash
# Stop the current Flask process (Ctrl+C in the terminal running it)
# Then restart from the project root:
python app.py
```

**Note:** Flask runs with `debug=True` (app.py line 620), which enables auto-reload, but some changes still require a manual restart.

---

### 2. Browser Cache
The browser might be using a cached version of the JavaScript.

**Solution:**
- Hard refresh: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
- Or clear browser cache for localhost:5000

---

### 3. Check Browser Console for Errors

**How to Check:**
1. Open browser developer tools (F12)
2. Go to "Console" tab
3. Click "Generate PDF" button
4. Look for any error messages in red

**Common errors and meanings:**
- `Failed to fetch` - Flask server not running
- `Unexpected token` - Server returned error HTML instead of JSON
- `404` - Route not found (unlikely with current code)

---

### 4. Check Flask Terminal Output

When you click "Generate PDF", the Flask terminal should show:
```
127.0.0.1 - - [DATE] "GET /generate-pdf/XXXXXXXX HTTP/1.1" 200 -
```

If you see `500` instead of `200`, there's a server error. Make sure app.py line 620 has:
```python
app.run(debug=True, port=5000)
```

---

### 5. Verify Session Data Exists

The PDF generator needs session data from the analysis step.

**Check if you:**
1. Uploaded an image
2. Clicked "Analyze Images" and waited for results
3. Are on the review.html page with results showing
4. Then clicked "Generate PDF"

If you jumped straight to PDF without analysis, there's no data to generate from.

---

## If Still Not Working

1. **Check the session_id:**
   - Open review.html
   - Check browser console: `console.log(sessionId)`
   - Should be an 8-character string like "a3f2b4c1"

2. **Manually test the route:**
   ```bash
   # In a new terminal while Flask is running:
   curl http://localhost:5000/generate-pdf/YOUR_SESSION_ID
   ```

3. **Check for Python errors:**
   Look at the Flask terminal for tracebacks when clicking the button

4. **Verify outputs folder exists:**
   ```bash
   mkdir outputs   # run from project root
   ```

---

## Expected Behavior

**Before clicking:** Button shows "📄 Generate PDF"
**While generating:** Button shows "⏳ Generating PDF..." and is disabled
**On success:**
- Button shows "✅ PDF Generated"
- Success message appears
- PDF file created in outputs/ folder

**On error:**
- Error message shown in red box
- Button shows "🔄 Retry PDF"
- Check Flask terminal for details

---

## Most Likely Solution

**Restart Flask server** - This fixes 90% of "button not working" issues after code changes.

Press Ctrl+C in terminal, then run:
```bash
python app.py
```
