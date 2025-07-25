# Grafana-PostgreSQL Deployment Guide

## Prerequisites

1. Two Ubuntu 22.04 VMs with SSH access
2. VMs should be in the same network for database connectivity
3. Ansible installed on control machine

## SSL Configuration (Context-Aware)

This template automatically detects your domain type and configures SSL appropriately:

### AWS Domains (*.amazonaws.com)
- **Automatically configured for HTTP-only**
- No SSL certificates needed (AWS owns the domain)
- Access via: `http://your-ec2-instance.amazonaws.com`
- Perfect for development and testing

### Custom Domains (yourdomain.com)
- **Automatically configured for HTTPS with Let's Encrypt**
- SSL certificates obtained and renewed automatically
- Access via: `https://grafana.yourdomain.com`
- Requires DNS pointing to your server

### Development Environments
- When environment is 'dev', 'local', or 'test': **HTTP-only by default**
- Override by setting `nginx_use_ssl: true` in config

## Deployment Steps

1. **Initialize project:**
   ```bash
   vm-config init grafana-postgres --env prod --output ./grafana-prod
   cd grafana-prod
   ```

2. **Configure environment:**
   - Edit `environments/prod/config.yml` with your VM details:
     ```yaml
     grafana_domain: "your-domain.com"     # For custom domain with SSL
     # OR
     grafana_domain: "ec2-xxx.amazonaws.com"  # For AWS domain (HTTP-only)
     
     nginx_use_ssl: true                   # Auto-detected, override if needed
     nginx_ssl_email: "admin@your-domain.com"  # For Let's Encrypt notifications
     ```
   - Copy `assets/vault-example.yml` to `vault-prod.yml`
   - Set secure passwords in vault file
   - Encrypt vault: `ansible-vault encrypt vault-prod.yml`

3. **Validate configuration:**
   ```bash
   vm-config validate --env prod
   ```

4. **Deploy:**
   ```bash
   vm-config apply --env prod
   ```

## Post-Deployment Access

### AWS Domain Setup
- Grafana: `http://your-ec2-instance.amazonaws.com`
- Default login: admin / (password from vault)
- No SSL setup required

### Custom Domain Setup
- Grafana: `https://grafana.yourdomain.com`
- SSL certificates automatically obtained
- HTTP redirects to HTTPS
- Default login: admin / (password from vault)

## Configuration Examples

### Development with AWS Instance
```yaml
environment: dev
grafana_domain: "ec2-13-60-190-242.eu-north-1.compute.amazonaws.com"
nginx_use_ssl: false  # Auto-detected as false
```

### Production with Custom Domain
```yaml
environment: prod
grafana_domain: "grafana.mycompany.com"
nginx_use_ssl: true   # Auto-detected as true
nginx_ssl_email: "admin@mycompany.com"
```

### Development Override (Force SSL)
```yaml
environment: dev
grafana_domain: "dev.mycompany.com"
nginx_use_ssl: true   # Override default dev behavior
nginx_ssl_email: "dev@mycompany.com"
```

## Troubleshooting

### General Issues
- Check container status: `docker ps`
- View logs: `docker logs grafana` or `docker logs postgres`
- Test connectivity: `telnet postgres-vm-ip 5432`

### SSL Issues (Custom Domains Only)
- Check certificate status: `certbot certificates`
- Test SSL: `openssl s_client -connect yourdomain.com:443`
- Renew manually: `certbot renew`
- Check nginx config: `nginx -t`

### AWS Domain Issues
- Ensure security groups allow port 80
- Check if EC2 instance has public IP
- Verify nginx is running: `systemctl status nginx`

### Log Locations
- Nginx: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`
- Let's Encrypt: `/var/log/letsencrypt/letsencrypt.log`
- Grafana: `docker logs grafana`

## Security Notes

- AWS domains use HTTP-only by design (AWS manages TLS termination)
- Custom domains automatically get HTTPS with proper certificates
- All configurations include security headers when SSL is enabled
- Firewall rules are automatically configured for required ports
