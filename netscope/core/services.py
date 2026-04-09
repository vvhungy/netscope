"""Service identification from IP addresses."""

# IP prefix -> service name mapping
_SERVICE_PREFIXES = [
    # Apple
    ("17.", "Apple"),
    # Dropbox
    ("162.125.", "Dropbox"),
    # Google
    ("142.250.", "Google"),
    ("142.251.", "Google"),
    ("64.233.", "Google"),
    ("66.102.", "Google"),
    ("66.249.", "Google"),
    ("72.14.", "Google"),
    ("74.125.", "Google"),
    ("108.177.", "Google"),
    ("209.85.", "Google"),
    ("216.58.", "Google"),
    ("216.239.", "Google"),
    # Google Cloud
    ("35.190.", "Google Cloud"),
    ("35.191.", "Google Cloud"),
    ("34.", "Google Cloud"),
    # GitHub
    ("140.82.", "GitHub"),
    ("192.30.", "GitHub"),
    ("185.199.", "GitHub"),
    # Cloudflare
    ("1.1.", "Cloudflare DNS"),
    ("1.0.", "Cloudflare DNS"),
    ("104.16.", "Cloudflare"),
    ("104.17.", "Cloudflare"),
    ("104.18.", "Cloudflare"),
    ("104.19.", "Cloudflare"),
    ("104.20.", "Cloudflare"),
    ("104.21.", "Cloudflare"),
    ("104.22.", "Cloudflare"),
    ("104.23.", "Cloudflare"),
    ("104.24.", "Cloudflare"),
    ("104.25.", "Cloudflare"),
    ("104.26.", "Cloudflare"),
    ("104.27.", "Cloudflare"),
    ("172.64.", "Cloudflare"),
    ("172.65.", "Cloudflare"),
    ("172.66.", "Cloudflare"),
    ("172.67.", "Cloudflare"),
    ("172.68.", "Cloudflare"),
    ("172.69.", "Cloudflare"),
    ("172.70.", "Cloudflare"),
    ("172.71.", "Cloudflare"),
    ("162.158.", "Cloudflare"),
    ("162.159.", "Cloudflare"),
    ("162.160.", "Cloudflare"),
    # Fastly
    ("151.101.", "Fastly"),
    ("199.232.", "Fastly"),
    # Akamai
    ("23.", "Akamai/CDN"),
    ("95.100.", "Akamai/CDN"),
    # AWS
    ("52.", "AWS"),
    ("54.", "AWS"),
    ("13.", "AWS"),
    ("3.", "AWS"),
    ("18.", "AWS"),
    # Azure
    ("40.", "Azure"),
    ("20.", "Azure"),
    ("51.", "Azure"),
    ("65.52.", "Azure"),
    # Telegram
    ("149.154.", "Telegram"),
    ("91.108.", "Telegram"),
    ("91.105.", "Telegram"),
    # Meta / Facebook
    ("157.240.", "Meta/Facebook"),
    ("31.13.", "Meta/Facebook"),
    ("66.220.", "Meta/Facebook"),
    # Slack
    ("54.191.", "Slack"),
    ("34.211.", "Slack"),
    ("52.72.", "Slack"),
    # Discord
    ("162.159.", "Discord"),
    ("188.114.", "Discord"),
    # Microsoft
    ("13.107.", "Microsoft"),
    ("40.126.", "Microsoft"),
    ("52.96.", "Microsoft"),
    # Netflix
    ("23.246.", "Netflix"),
    ("37.77.", "Netflix"),
    ("45.57.", "Netflix"),
    # Spotify
    ("35.186.", "Spotify"),
    ("104.199.", "Spotify"),
]


def identify_service(ip: str) -> str | None:
    """
    Identify the service associated with an IP address.

    Args:
        ip: IPv4 address string

    Returns:
        Service name (e.g., "Google", "AWS") or None if unknown
    """
    for prefix, name in _SERVICE_PREFIXES:
        if ip.startswith(prefix):
            return name
    return None
