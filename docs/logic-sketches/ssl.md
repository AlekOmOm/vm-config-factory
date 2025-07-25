# logic sketch for SSL optionality

current implementation gives user option of using SSL or not for their nginx config.

current input:
- if domain is custom domain, then use SSL
   - 'custom domain' is defined as a domain that is not an AWS domain (*.amazonaws.com)

premise:
- dev env can thus have SSL enabled
    - since they can be using AWS or Custom domain

## Current Implementation (FLAWED):
```python
is_dev = environment in ['dev', 'local', 'test']
nginx_use_ssl: False if is_dev else True
```

**Problem**: Environment type ≠ SSL capability
- Dev environments can use custom domains (SSL possible)
- Prod environments can use AWS domains (SSL not possible)

## Correct Implementation:
```python
# SSL decision should be based on DOMAIN TYPE, not environment type
is_aws_domain = 'amazonaws.com' in grafana_domain or 'compute.internal' in grafana_domain
nginx_use_ssl = not is_aws_domain  # SSL only for custom domains

# Environment only affects DEFAULT domain suggestion
default_domain = 'localhost' if is_dev else 'grafana.example.com'
```

## Logic Matrix:
| Environment | Domain Type | SSL | Example |
|-------------|-------------|-----|---------|
| dev | AWS | ❌ | `ec2-xxx.amazonaws.com` |
| dev | Custom | ✅ | `dev.mycompany.com` |
| prod | AWS | ❌ | `ec2-xxx.amazonaws.com` |
| prod | Custom | ✅ | `grafana.mycompany.com` |

## User Control:
Users can override by setting:
```yaml
grafana_domain: "dev.mycompany.com"  # Custom domain in dev
nginx_use_ssl: true                  # Force SSL even if auto-detected as false
```
