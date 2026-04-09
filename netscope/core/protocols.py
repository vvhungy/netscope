"""Protocol classification based on port numbers."""

# Well-known TCP ports and their service names
_TCP_PORTS = {
    # Web protocols
    80: "HTTP",
    443: "HTTPS",
    8080: "HTTP-Alt",
    8000: "HTTP-Alt",
    8888: "HTTP-Alt",
    3000: "HTTP-Dev",
    5000: "HTTP-Dev",

    # Remote access
    22: "SSH",
    23: "Telnet",
    3389: "RDP",
    5900: "VNC",
    5901: "VNC",
    5902: "VNC",

    # Email protocols
    25: "SMTP",
    465: "SMTPS",
    587: "SMTP-TLS",
    110: "POP3",
    995: "POP3S",
    143: "IMAP",
    993: "IMAPS",

    # File transfer
    20: "FTP-Data",
    21: "FTP",
    69: "TFTP",
    989: "FTPS-Data",
    990: "FTPS",
    115: "SFTP",
    139: "NetBIOS",
    445: "SMB",

    # Database
    3306: "MySQL",
    5432: "PostgreSQL",
    1433: "MSSQL",
    1521: "Oracle-DB",
    27017: "MongoDB",
    6379: "Redis",
    5672: "RabbitMQ",
    9042: "Cassandra",
    5984: "CouchDB",
    9200: "Elasticsearch",
    2424: "OrientDB",

    # Messaging
    1883: "MQTT",
    8883: "MQTTS",
    5222: "XMPP",
    5269: "XMPP-Server",
    6667: "IRC",
    6697: "IRC-TLS",

    # DNS and networking
    53: "DNS",
    123: "NTP",
    161: "SNMP",
    162: "SNMP-Trap",
    389: "LDAP",
    636: "LDAPS",
    67: "DHCP-Server",
    68: "DHCP-Client",

    # Media streaming
    1935: "RTMP",
    1936: "RTMPS",
    8554: "RTSP",
    554: "RTSP",
    5004: "RTP",
    5005: "RTCP",

    # VPN and tunneling
    1194: "OpenVPN",
    1723: "PPTP",
    500: "IKE",
    4500: "IPSec-NAT",
    1701: "L2TP",

    # Proxy and caching
    3128: "Squid",
    1080: "SOCKS",
    8118: "Privoxy",
    9040: "Tor",

    # Version control
    9418: "Git",

    # Gaming
    25565: "Minecraft",
    27015: "Source-Game",
    27016: "Source-Game",
    27018: "Source-Game",
    27019: "Source-Game",
    27020: "Source-Game",
    7777: "Game-Server",
    27000: "Steam",

    # Monitoring and logging
    514: "Syslog",
    601: "Syslog-TLS",
    8125: "StatsD",
    9090: "Prometheus",
    9093: "Alertmanager",
    3100: "Loki",

    # Other common services
    111: "RPCBind",
    2049: "NFS",
    6000: "X11",
    6001: "X11",
    6002: "X11",
    873: "RSync",
    179: "BGP",
    51413: "Transmission",
    6881: "BitTorrent",
}

# Well-known UDP ports and their service names
_UDP_PORTS = {
    # DNS and networking
    53: "DNS",
    123: "NTP",
    161: "SNMP",
    162: "SNMP-Trap",
    67: "DHCP-Server",
    68: "DHCP-Client",
    514: "Syslog",
    500: "IKE",
    4500: "IPSec-NAT",
    1701: "L2TP",

    # Media streaming
    5004: "RTP",
    5005: "RTCP",
    554: "RTSP",

    # Gaming (often UDP)
    25565: "Minecraft",
    27015: "Source-Game",
    27016: "Source-Game",
    27018: "Source-Game",
    27019: "Source-Game",
    27020: "Source-Game",
    7777: "Game-Server",
    27000: "Steam",
    3478: "STUN",
    5349: "TURN-TLS",

    # VPN
    1194: "OpenVPN",
    51820: "WireGuard",
    443: "OpenVPN-UDP",

    # VoIP
    5060: "SIP",
    5061: "SIP-TLS",
    10000: "SIP-RTP",

    # Other
    111: "RPCBind",
    137: "NetBIOS-NS",
    138: "NetBIOS-DGM",
    51413: "Transmission",
    6881: "BitTorrent",
    1900: "UPnP",
    5353: "mDNS",
    8125: "StatsD",
}


def classify_protocol(port: int, is_udp: bool = False) -> str:
    """
    Classify a port number to its protocol/service name.

    Args:
        port: The port number to classify
        is_udp: True if UDP, False if TCP (default)

    Returns:
        The protocol name (e.g., "HTTPS", "DNS") or "port-N" for unknown ports
    """
    port_map = _UDP_PORTS if is_udp else _TCP_PORTS

    if port in port_map:
        return port_map[port]

    # For some protocols, check the other protocol map as fallback
    # DNS can run over both TCP and UDP
    if port == 53:
        return "DNS"
    # NTP is typically UDP but some implementations use TCP
    if port == 123:
        return "NTP"
    # HTTP/HTTPS can technically be UDP with HTTP/3
    if port == 443 and is_udp:
        return "HTTP/3"

    return f"port-{port}"


def get_well_known_ports(protocol: str) -> list[int]:
    """
    Get the well-known port(s) for a protocol name.

    Args:
        protocol: The protocol name (case-insensitive)

    Returns:
        List of port numbers associated with this protocol
    """
    protocol_upper = protocol.upper()
    ports = []

    for port, name in _TCP_PORTS.items():
        if name.upper() == protocol_upper:
            ports.append(port)

    for port, name in _UDP_PORTS.items():
        if name.upper() == protocol_upper and port not in ports:
            ports.append(port)

    return sorted(ports)


def is_well_known_port(port: int) -> bool:
    """
    Check if a port is a well-known service port.

    Args:
        port: The port number to check

    Returns:
        True if the port is in the well-known ports list
    """
    return port in _TCP_PORTS or port in _UDP_PORTS
