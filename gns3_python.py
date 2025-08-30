import gns3fy

# Define the server object to establish the connection
gns3_server = gns3fy.Gns3Connector("http://172.16.194.131:80")

# Define the lab you want to load and assign the server connector
lab = gns3fy.Project(name="test-gns3-api", connector=gns3_server)

# Retrieve its information and display
lab.get()
print(lab)
# Project(project_id='4b21dfb3-675a-4efa-8613-2f7fb32e76fe', name='test-gns3-api', status='opened', ...)

# Access the project attributes
print(f"Name: {lab.name} -- Status: {lab.status} -- Is auto_closed?: {lab.auto_close}")
# Name: test-gns3-api -- Status: closed -- Is auto_closed?: False

# Open the project
lab.open()
print(lab.status)
# opened

# Verify the stats
print(lab.stats)
# {'drawings': 0, 'links': 4, 'nodes': 6, 'snapshots': 0}

# List the names and status of all the nodes in the project
for node in lab.nodes:
	print(f"Node: {node.name} -- Node Type: {node.node_type} -- Status: {node.status}")

# Node: Ethernetswitch-1 -- Node Type: ethernet_switch -- Status: started