from . import base

for k, v in base.__dict__.items():
    if k.isupper():
        globals()[k] = v

# Production overrides placeholder (extend as needed)
