# Okta SSO & Account Lockout Policy

## Account Lockout Rules
- Accounts are locked automatically after 5 consecutive incorrect password entries.
- Self-service unlock is available via Okta verify push notification.

## Troubleshooting Password Resets & Authentication Errors (ERR_OUTLOOK_SAML)
If locked out of your Okta SSO account or experiencing SAML token expiration in Microsoft Outlook:
1. Navigate to `https://sso.acme-corp.com/help`.
2. Click **Unlock Account** or **Forgot Password**.
3. Complete MFA via SMS or Okta Verify app.
4. Clear browser cookies and SAML tokens for `acme-corp.com`.
5. Passwords must be at least 16 characters long and include numbers and special characters.
