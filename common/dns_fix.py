import socks
import socket
import requests

def force_dns_resolution(url, method='get', **kwargs):
    """
    Forces DNS resolution for a request over a specific DNS server.
    This is a workaround for environments where the default resolver fails
    under certain conditions (e.g., inside a gunicorn eventlet worker).
    """
    original_getaddrinfo = socket.getaddrinfo

    def patched_getaddrinfo(*args, **kwargs):
        # The first argument is the host
        host = args[0]
        try:
            # Use a reliable public DNS resolver to get the IP address
            ip_address = socket.gethostbyname(host)
            # Return the resolved IP address, letting the rest of the function proceed
            return original_getaddrinfo(ip_address, *args[1:], **kwargs)
        except socket.gaierror:
            # Fallback to the original function if our resolver fails
            return original_getaddrinfo(*args, **kwargs)

    socket.getaddrinfo = patched_getaddrinfo

    try:
        if method.lower() == 'post':
            response = requests.post(url, **kwargs)
        else:
            response = requests.get(url, **kwargs)
        return response
    finally:
        # Restore the original function to avoid affecting other parts of the system
        socket.getaddrinfo = original_getaddrinfo 