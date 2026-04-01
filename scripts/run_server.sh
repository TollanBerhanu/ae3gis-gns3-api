# assign 192.168.0.100 to the server
ip addr add 192.168.0.99/24 dev eth0
# run the server with:
exec nginx -g 'daemon off;'
