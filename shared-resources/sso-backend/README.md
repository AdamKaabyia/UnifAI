Below is the flowchart of the SSO flow.

A few notes:
1. 2 routes are being used, one for the main app and one for the sso authmanager pod
2. currently we only used directly a flask server with the auth manager.


![Alt text](unifai_sso.png "unifai SSO flow")


the flow chart was created using the site [sequencediagram](https://sequencediagram.org/)
the chart text is below:


```
title Unifai SSO process

User->Nginx: get UI client files (frontend_url)
Nginx->User: send UI client files
note over User,Nginx:Client automaticaly send API call to start login process
User->Nginx: frontend_url/api3/auth/login
Nginx->User: redirect to sso-be-url/api/auth/login
User->sso-be: sso-be-url/api/auth/login
sso-be->User: redirect to RH-SSO
note over User,sso-be:redirect url: sso-be/api/callback
User->RH-sso: login process
RH-sso->User: redirect to sso-be/api/callback
sso-be->User: redirect to frontend_url?auth=success
User->Nginx: browse pages (frontend_url/api1 | frontend_url/api2)
```

## Logout and login (GENIE-827)

- **`POST /api/auth/logout`** — Clears the server-side session and cookie, and **best-effort** calls Keycloak’s **OpenID Connect logout** with the stored **refresh token** so the SSO session can be ended server-side, not only in the browser.
- **Login page** — The UI serves **`/login`** with a single **SSO** action; that route is outside the authenticated shell so users can open it while logged out.