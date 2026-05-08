# 🚀 איך לשחרר גרסה חדשה של אילתוש

## TL;DR — Push to main = New Build Automatically

### האפשרות הקלה: דחיפה אוטומטית
1. כל שינוי בקוד שאתה דוחף ל-`main` בענף בריפו GitHub יפעיל בנייה אוטומטית.
2. בנייה רצה ב-Expo (~15-20 דקות).
3. כשהיא מסתיימת תקבל מייל מ-Expo עם קישור הורדה ל-`.aab`.
4. אתה מעלה את ה-`.aab` ל-Google Play Console (Internal Testing → Create release → Upload).

### האפשרות הידנית: כפתור "Run workflow"
אם רוצה לבנות בלי לדחוף קוד:
1. כנס ל: https://github.com/levkazaryan/Eilatush/actions/workflows/android-build.yml
2. לחץ על כפתור **"Run workflow"** מימין
3. בחר branch `main` → לחץ **Run workflow**
4. אותה תוצאה — בנייה ב-Expo, מייל עם `.aab`.

---

## איפה לראות סטטוס

| מה | איפה |
|----|------|
| GitHub Actions runs | https://github.com/levkazaryan/Eilatush/actions |
| EAS builds (Expo) | https://expo.dev/accounts/levkazaryan/projects/eilatush/builds |
| Play Console | https://play.google.com/console |

---

## לעלות ל-Play Console (ידני, ~30 שניות)

1. כשהבנייה מסתיימת ב-Expo → לחץ "Download" → תוריד `application.aab`.
2. Play Console → Eilatush → **Internal testing** → **Create new release**.
3. גרור את ה-`.aab` לתיבת ההעלאה.
4. כתוב Release notes קצרים בעברית.
5. **Save → Review release → Start rollout**.
6. אחרי 5-10 דקות, גרסה חדשה זמינה ל-testers.

---

## הסודות שמוגדרים בריפו

GitHub repo: https://github.com/levkazaryan/Eilatush/settings/secrets/actions

- `EXPO_TOKEN` ✅ מוגדר (token של חשבון `levkazaryan` ב-Expo)
- `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` ⚠️ עדיין לא — נחוץ רק אם רוצים auto-submit ל-Play Store

---

## הוספת auto-submit ל-Play Store (אופציונלי, מאוחר יותר)

כשתהיה לך זמן (10 דק'), נגדיר Service Account ב-Google Cloud כדי ש-EAS ישלח את ה-`.aab` ל-Play Console אוטומטית. אז גם ההעלאה הידנית תהפוך לאוטומטית. עד אז — הצעד היחיד הידני הוא הגרירה של ה-`.aab` ל-Play Console.

---

## תקלות נפוצות

### Build Failed ב-GitHub Actions
- כנס ל-Actions → Run האחרון → קרא את ה-log
- שגיאה הכי נפוצה: בעיית package.json — ודא שהוספת חבילות חדשות עם `yarn add`.

### Build Failed ב-EAS
- כנס ל-Expo dashboard build → קרא log
- בדרך כלל: שגיאת build native (חבילה לא תואמת ל-Expo SDK)

### App Empty After Install
- בדוק ש-`eas.json` מכיל `EXPO_PUBLIC_BACKEND_URL` תחת `production.env`
- בדוק שה-backend חי: `curl https://eilat-connect.emergent.host/api/events?limit=1`
