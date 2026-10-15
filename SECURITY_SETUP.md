# OpenAI configuration

Set `OPENAI_API_KEY` in the environment before starting the Python programs. The OpenAI SDK reads this variable automatically; no key belongs in source code. Use your local secret manager or deployment secret configuration. A `.env` file is not loaded automatically by these scripts.

The removed credentials remain in Git history. Their owner must revoke or rotate them in OpenAI; this change does not revoke credentials or remove history.
