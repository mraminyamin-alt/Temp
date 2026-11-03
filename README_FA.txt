# TempMail Pro APK project

This project builds an Android APK using Kivy + Buildozer and GitHub Actions.

## Build on a phone (no PC required)

1. Create a GitHub account and a new **public** repository named `TempMail-Pro`.
2. Upload `main.py`, `buildozer.spec`, and `.github/workflows/build.yml` keeping the folder structure.
3. Open the repository's **Actions** tab.
4. Select **Build TempMail Pro APK** and press **Run workflow**.
5. Wait for the workflow to finish successfully.
6. Open the completed workflow run, find **Artifacts**, and download `TempMail-Pro-APK`.
7. Extract the ZIP and install the APK on Android. You may need to allow installation from your browser/files app.

## Important

- The app uses the Mail.tm API and requires internet access.
- Email accounts/tokens are stored locally in the app's private SQLite database.
- The delete button removes an account from this app's local list; it does not delete the remote Mail.tm account.
- This is a debug APK for personal testing, not a Play Store release.
- Do not publish tokens, passwords, or screenshots containing private messages.
- Some websites block temporary email domains.