"""Fixed income formulas.

Conventions:
- Rates are decimals. Annual rates are nominal and compounded at the stated frequency unless the
  function says "effective".
- Bond yields follow the bond-equivalent convention: periodic yield = annual yield / frequency.
- v1 prices bonds on coupon dates only (no accrued interest, no day count): years × frequency
  must be a whole number of periods.
"""
