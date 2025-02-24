import sys
import yaml
import json

def generate_docker_compose(num_nodes, client_nums, state_name):
    services = {}
    network_name = 'raft-common-network'
    
    host_base_sub_ip_node = '10.0.0'
    host_base_port_node = 3333
    host_base_port_client = 5555

    node_portlist = {}
    clients = ",".join([ f"client{i}" for i in range(1, client_nums + 1)])

    for i in range(1, num_nodes + 1):
        node_name = f'node{i}'
        cluster = ','.join([f'node{j}' for j in range(1, num_nodes + 1) if j != i])
        ipv4_address = f'{host_base_sub_ip_node}.{i+1}'
        host_port = host_base_port_node + i - 1
        services[node_name] = {
            'build': '.',
            'container_name': node_name,
            'environment': [
                f'NODE={node_name}',
                f'CLUSTER={cluster}',
                f'CLIENTS={clients}'
            ],
            'ports': [f'{host_port}:8080/udp'],
            'command': ["python", "-m", "raft.run_node", "--node", ipv4_address, "--cluster", cluster, "--name", node_name, "--clients", clients, "--state", state_name],
            'networks': {
                network_name: {
                    'ipv4_address': ipv4_address
                }
            }
        }
        node_portlist[node_name] = {
            'host': ipv4_address,
            'export_port': host_port,
            'internal_port': 8080
        }

    for i in range(num_nodes + 1, num_nodes + client_nums + 1):
        client_name = f'client{i - num_nodes}'
        host_port = host_base_port_client + i - 1
        ipv4_address = f"{host_base_sub_ip_node}.{i+1}"
        services[client_name] = {
            'build': '.',
            'container_name': client_name,
            'command': ["python", "-m", "client.run_client", "--name", client_name, "--client", state_name],
            'ports': [f'{host_port}:8888/udp'],
            'networks': {
                network_name: {
                    'ipv4_address': ipv4_address
                }
            },
            'depends_on': {
                f'node{num_nodes}': {
                    'condition': 'service_started'
                }
            }
        }
        node_portlist[client_name] = {
            'host': ipv4_address,
            'export_port': host_port,
            'internal_port': 8888
        }

    docker_compose = {
        'version': '3.8',
        'services': services,
        'networks': {
            network_name: {
                'driver': 'bridge',
                'ipam': {
                    'driver': 'default',
                    'config': [
                        {'subnet': f'{host_base_sub_ip_node}.0/24'},
                    ]
                }
            },
        }
    }


    # Write the docker-compose.yml file
    with open('docker-compose.yml', 'w') as file:
        yaml.dump(docker_compose, file, default_flow_style=False)
    print(f'docker-compose.yml with {num_nodes} nodes and {num_clients} clients generated successfully.')

    with open('node_portlist.json', 'w') as file:
        json.dump(node_portlist, file, indent=4)
    print(f'node_portlist.json with {num_nodes} nodes and {num_clients} clients generated successfully.')

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python generate_docker_compose.py <number_of_nodes (< 254)> <number_of_clients (< 254)> <state_name>")
        sys.exit(1)

    try:
        num_nodes = int(sys.argv[1])
        if num_nodes < 1 or num_nodes > 253:
            raise ValueError
        num_clients = int(sys.argv[2])
        if num_clients < 1 or num_clients > 253:
            raise ValueError
        state_name = sys.argv[3]
        generate_docker_compose(num_nodes, num_clients, state_name)
    except ValueError:
        print("Please provide a valid integer for the number of nodes (< 254) and clients (< 254).")
        sys.exit(1)
