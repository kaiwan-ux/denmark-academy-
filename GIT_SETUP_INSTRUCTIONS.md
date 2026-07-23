# Git Setup Instructions - Denmark Academy

## ✅ Commit Successfully Created!

Your Danish audio library has been committed to the local Git repository.

**Commit Details:**
- Commit Hash: `6cda1d1`
- Message: "Add Danish PR and citizenship audio library"
- Branch: `master`
- Files committed: 38 files (3 code files + 35 MP3 audio files)
- Total size: ~563 MB

---

## Files Committed

### Code Files:
1. `frontend/app/audio/page.tsx` - Main audio library page
2. `frontend/app/globals.css` - Updated global styles
3. `frontend/components/app-shell.tsx` - Updated navigation with Audio link

### Audio Files:
**Citizenship (Indfødsretsprøven):** 8 recordings
- `frontend/public/audio/citizenship/chp-1-part-1.mp3`
- `frontend/public/audio/citizenship/chp-1-part-2.mp3`
- `frontend/public/audio/citizenship/chp-2.mp3`
- `frontend/public/audio/citizenship/chp-3.mp3`
- `frontend/public/audio/citizenship/chp-4.mp3`
- `frontend/public/audio/citizenship/chp-5.mp3`
- `frontend/public/audio/citizenship/chp-6-part-1.mp3`
- `frontend/public/audio/citizenship/chp-6-part-2.mp3`

**PR (Medborgerskabsprøven):** 27 recordings
- `frontend/public/audio/pr/mp-indledning.mp3`
- `frontend/public/audio/pr/mp-faktaark-1.mp3` through `mp-faktaark-26.mp3`

---

## Next Steps: Push to Remote Repository

Currently, there is **no remote repository configured**. You need to add your remote repository before pushing.

### Option 1: Push to GitHub

```bash
# Add your GitHub repository as remote
git remote add origin https://github.com/YOUR_USERNAME/denmark-academy.git

# Push to GitHub (first time)
git push -u origin master

# Or if your main branch is called 'main', rename it first:
git branch -M main
git push -u origin main
```

### Option 2: Push to GitLab

```bash
# Add your GitLab repository as remote
git remote add origin https://gitlab.com/YOUR_USERNAME/denmark-academy.git

# Push to GitLab
git push -u origin master
```

### Option 3: Push to Bitbucket

```bash
# Add your Bitbucket repository as remote
git remote add origin https://bitbucket.org/YOUR_USERNAME/denmark-academy.git

# Push to Bitbucket
git push -u origin master
```

### Option 4: Push to Azure DevOps

```bash
# Add your Azure DevOps repository as remote
git remote add origin https://dev.azure.com/YOUR_ORG/denmark-academy/_git/denmark-academy

# Push to Azure DevOps
git push -u origin master
```

---

## Important Notes

### Large File Upload (563 MB)
⚠️ **The audio files are approximately 563 MB in total**. The first push may take several minutes depending on your internet connection.

### Git LFS (Large File Storage) - Optional
If you encounter issues with large files, consider using Git LFS:

```bash
# Install Git LFS (if not already installed)
git lfs install

# Track MP3 files with LFS
git lfs track "*.mp3"

# Add .gitattributes file
git add .gitattributes

# Re-add and commit
git add frontend/public/audio/**/*.mp3
git commit -m "Track audio files with Git LFS"
```

### GitHub File Size Limits
- **GitHub**: Free plans have a 100 MB file size limit per file. Your audio files should be fine if each is under 100 MB.
- **GitHub with LFS**: Supports up to 2 GB per file, with 1 GB free storage per month.

---

## Verify Your Commit

```bash
# Check commit log
git log --oneline

# Check what files were committed
git show --stat HEAD

# Check repository status
git status
```

---

## Create Remote Repository (If You Haven't)

### GitHub:
1. Go to https://github.com/new
2. Repository name: `denmark-academy`
3. Make it Private or Public
4. **DO NOT** initialize with README, .gitignore, or license (you already have files)
5. Click "Create repository"
6. Follow the "push an existing repository" instructions

### GitLab:
1. Go to https://gitlab.com/projects/new
2. Select "Create blank project"
3. Project name: `denmark-academy`
4. Set visibility level
5. **Uncheck** "Initialize repository with a README"
6. Click "Create project"
7. Follow the "Push an existing Git repository" instructions

---

## After Pushing

Once you've pushed to your remote repository:

1. **Verify on the web interface** that all files uploaded successfully
2. **Check the audio files** are accessible at:
   - `/audio/citizenship/chp-1-part-1.mp3`
   - `/audio/pr/mp-indledning.mp3`
   - etc.

3. **Deploy to your hosting platform:**
   - **Vercel**: Connect your GitHub/GitLab repo and deploy
   - **Netlify**: Import your repository
   - **AWS Amplify**: Connect your Git provider
   - **Custom server**: `git pull` on your server

---

## Deployment Considerations

### Static Site Generation
The `/audio` page is **statically generated** during build time, which is perfect for deployment.

### CDN Optimization
For better performance with large audio files:
1. Consider hosting MP3 files on a CDN (Cloudflare, AWS CloudFront)
2. Update audio URLs in `frontend/app/audio/page.tsx`
3. Enable cache headers for audio files (already configured in `next.config.js`)

### Build Command
```bash
cd frontend
npm install
npm run build
```

---

## Troubleshooting

### "Repository not found" error
Make sure you've created the remote repository first and are using the correct URL.

### Authentication issues
- **HTTPS**: Use Personal Access Token instead of password
- **SSH**: Set up SSH keys (`ssh-keygen` and add to GitHub/GitLab)

### Large file errors
If you get "file too large" errors, use Git LFS (see instructions above).

### Slow upload
The 563 MB of audio will take time. Be patient during the first push.

---

## Summary

✅ **Local commit created successfully**  
⚠️ **No remote repository configured yet**  
📝 **Next action**: Add remote repository and push

**Command to check status:**
```bash
git status
git remote -v
```

**Quick push (once remote is added):**
```bash
git push -u origin master
# or
git push -u origin main
```

---

*Generated: 2026-07-23*  
*Commit: 6cda1d1*
