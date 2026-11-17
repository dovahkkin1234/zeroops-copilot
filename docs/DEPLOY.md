# Deploying the Demo Page

The demo page lives in `site/index.html` — a single static file with no build step.
You drag the folder (or link the repo) to a free static host and get a public URL.

**Requirement:** The URL must open without sign-in and work on a phone.
Do not use `github.io` — the application form rejects GitHub-domain links.

---

## Option A — Netlify Drop (fastest, no account needed)

1. Open <https://app.netlify.com/drop> in your browser.
2. Open your file manager, navigate to `zeroops-copilot/site/`.
3. Drag the **`site/` folder** (the whole folder, not the file inside it) onto the Netlify
   drop zone. Wait about 10 seconds.
4. Netlify shows a URL like `https://grand-narwhal-abc123.netlify.app`.
5. Open that URL in a **private/incognito window** (a different browser if possible).
6. Test on your phone: open the URL, click **Analyze** after picking a fixture, and verify
   the model loads and produces results.
7. Submit that URL.

**To update later** (if you make changes):
- Create a free Netlify account, claim the site (there is a "Claim site" button on the
  drop result page), and then use `netlify deploy --dir site --prod` from the CLI, or
  drag the updated `site/` folder again from the Netlify dashboard.

---

## Option B — Cloudflare Pages (permanent URL, needs GitHub push)

1. Push the branch to GitHub: `git push origin polish-msr`.
2. Go to <https://dash.cloudflare.com/> and create a free account (or log in).
3. Click **Workers & Pages → Create application → Pages → Connect to Git**.
4. Authorize Cloudflare to read the repo. Select `zeroops-copilot`.
5. Settings:
   - **Build command:** leave blank
   - **Build output directory:** `site`
   - **Root directory:** leave blank
6. Click **Save and Deploy**. Cloudflare builds in about 15 seconds.
7. The URL will be `https://zeroops-copilot.pages.dev` (or a variant if that name is taken).
   Verify in incognito and on a phone.

**To update:** `git push origin polish-msr`. Cloudflare automatically redeploys on push.

---

## Option C — Vercel (also permanent, also needs GitHub push)

1. Push the branch to GitHub.
2. Go to <https://vercel.com> and create a free account.
3. Click **Add New → Project → Import Git Repository** → select `zeroops-copilot`.
4. Under **Framework Preset** choose "Other".
   Under **Output Directory** type `site`.
   Leave **Build Command** blank.
5. Click **Deploy**. The URL looks like `https://zeroops-copilot.vercel.app`.
6. Verify in incognito and on a phone.

---

## Verification checklist

Run through this in a private/incognito window before submitting:

- [ ] Page loads without signing in
- [ ] No console errors (open DevTools → Console)
- [ ] V0 research banner is visible
- [ ] All five fixture buttons fill the textarea correctly
- [ ] Clicking **Analyze** shows a progress bar then produces results
  (first load downloads ~25 MB of ONNX model weights — takes 10–30 s depending on connection)
- [ ] Similarity scores and triage verdict appear
- [ ] Save-contract widget rejects confidence < 0.5 and status = "uncertain"
- [ ] Duplicate error text produces "upserted, not inserted" on second save
- [ ] Page is usable at 375 px width (phone) with no horizontal scroll
- [ ] No `.env` contents, no API keys visible in page source (Cmd/Ctrl+U)
- [ ] The evaluation section shows real benchmark results (n=3 runs, qwen2.5:7b, Ollama)

---

## Notes

- The model (`Xenova/all-MiniLM-L6-v2`) is downloaded from Hugging Face CDN on first use,
  cached by the browser for subsequent visits. It is ~23 MB. No server or key required.
- The page uses no `localStorage`, no cookies, no analytics, and no external requests
  beyond the transformers.js CDN and the Hugging Face model CDN.
- If a reviewer visits from a restricted network where HuggingFace CDN is blocked,
  the page shows a fallback message and the rest of the page (save contract, architecture,
  limitations) still works.
