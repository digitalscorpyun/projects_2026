# mini_recon.ps1
# Local Host Recon — N+ Learning Script
# Maps to: West Ch.10 Scanning Tools p.561
# What this script discovers mirrors what Nmap discovers about a host:
#   - Network interfaces and IP addresses
#   - DNS servers
#   - Open/listening ports

Write-Host "`n=== LOCAL HOST RECON ===" -ForegroundColor Cyan
Write-Host "Simulating what a scanning tool discovers about this machine" -ForegroundColor DarkGray
Write-Host ""

# --- 1. Network Interfaces ---
# Nmap discovers: every available host, IP addresses, subnet info
Write-Host "--- NETWORK INTERFACES ---" -ForegroundColor Yellow
Get-NetIPConfiguration |
    Where-Object { $_.IPv4Address } |
    Select-Object InterfaceAlias,
                  @{Name='IPv4Address'; Expression={ $_.IPv4Address.IPAddress }},
                  @{Name='Gateway';     Expression={ $_.IPv4DefaultGateway.NextHop }} |
    Format-Table -AutoSize

# --- 2. DNS Servers ---
# Nmap/Nessus discover: DNS configuration for the host
Write-Host "--- DNS SERVERS ---" -ForegroundColor Yellow
Get-DnsClientServerAddress -AddressFamily IPv4 |
    Where-Object { $_.ServerAddresses } |
    Select-Object InterfaceAlias, ServerAddresses |
    Format-Table -AutoSize

# --- 3. Listening Ports ---
# This is what a port scanner finds: open ports indicating active services
# Compare: Nmap's core function is exactly this
Write-Host "--- LISTENING PORTS (open = potential attack surface) ---" -ForegroundColor Yellow
Get-NetTCPConnection -State Listen |
    Select-Object LocalAddress, LocalPort |
    Sort-Object LocalPort |
    Format-Table -AutoSize

Write-Host "=== END RECON ===" -ForegroundColor Cyan
Write-Host "Source: West Ch.10 p.561 - Scanning Tools" -ForegroundColor DarkGray
Write-Host ""
