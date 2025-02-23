import sys
import yaml
import json

def generate_docker_compose(num_nodes, client_nums):
    services = {}
    network_node_name = 'raft-node-network'
    network_client_name = 'raft-client-network'
    
    host_base_sub_ip_node = '10.0.0'
    host_base_sub_ip_client = '10.0.1'
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
            'command': ["python", "-m", "raft.run_node", "--node", ipv4_address, "--cluster", cluster, "--name", node_name, "--clients", clients],
            'networks': {
                network_node_name: {
                    'ipv4_address': ipv4_address
                }
            }
        }
        node_portlist[node_name] = host_port

    for i in range(1, client_nums + 1):
        client_name = f'client{i}'
        cluster = ','.join([f'node{j}' for j in range(1, num_nodes + 1)])
        ipv4_address = f'{host_base_sub_ip_client}.{i+1}'
        host_port = host_base_port_client + i - 1
        services[client_name] = {
            'build': '.',
            'container_name': client_name,
            'command': ["python", "-m", "client.run_client", "--node", ipv4_address, "--cluster", cluster, "--name", client_name],
            'ports': [f'{host_port}:8888/udp'],
            'networks': {
                network_client_name: {
                    'ipv4_address': ipv4_address
                }
            }
        }
        node_portlist[client_name] = host_port

    docker_compose = {
        'version': '3.8',
        'services': services,
        'networks': {
            network_node_name: {
                'driver': 'bridge',
                'ipam': {
                    'driver': 'default',
                    'config': [
                        {'subnet': f'{host_base_sub_ip_node}.0/24'}
                    ]
                }
            },
            network_client_name: {
                'driver': 'bridge',
                'ipam': {
                    'driver': 'default',
                    'config': [
                        {'subnet': f'{host_base_sub_ip_client}.0/24'}
                    ]
                }
            }
        }
    }


    # Write the docker-compose.yml file
    with open('docker-compose.yml', 'w') as file:
        yaml.dump(docker_compose, file, default_flow_style=False)
    print(f'docker-compose.yml with {num_nodes} nodes and {num_clients} clients generated successfully.')

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python generate_docker_compose.py <number_of_nodes (< 254)> <number_of_clients (< 254)>")
        sys.exit(1)

    try:
        num_nodes = int(sys.argv[1])
        if num_nodes < 1 or num_nodes > 253:
            raise ValueError
        num_clients = int(sys.argv[2])
        if num_clients < 1 or num_clients > 253:
            raise ValueError
        generate_docker_compose(num_nodes, num_clients)
    except ValueError:
        print("Please provide a valid integer for the number of nodes (< 254) and clients (< 254).")
        sys.exit(1)
