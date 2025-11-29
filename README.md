# Public Goods Firms (oTree)

This repository contains an oTree implementation of the "Public Good Provision with Endogenous Groups" study. Sessions are configured for the four treatment combinations listed in `settings.py`.

## Quickstart

1. Install dependencies (Python 3.10+ recommended):

   ```bash
   pip install -r requirements.txt
   ```

2. Set an admin password for the oTree admin interface (for example, in your shell):

   ```bash
   export OTREE_ADMIN_PASSWORD=changeme
   ```

3. Start the oTree development server:

   ```bash
   otree devserver
   ```

4. In your browser, open `http://localhost:8000/` and create a session using one of the preset configurations:

   - `pg_exo_const`: exogenous firms, constant returns
   - `pg_exo_incr`: exogenous firms, increasing returns
   - `pg_endo_const`: endogenous firms, constant returns
   - `pg_endo_incr`: endogenous firms, increasing returns

For a quick syntax check without running the server, you can run:

```bash
python -m compileall public_goods_firms
```

## Notes
- Default participation fees and conversion rates are defined in `settings.py`. Adjust them if you want payments to match your lab budget.
- Session sizes are set to 20 (exogenous) or 18 (endogenous) participants to mirror the design described in the accompanying research description.
