from flask import Flask, jsonify, render_template
from threading import Thread

class FlaskVisualizer:
    def __init__(self, community, port=8080):
        self.community = community
        self.port = port
        self.app = Flask(__name__)
        
        # Setup routes
        self.app.add_url_rule('/', 'index', self.get_index)
        self.app.add_url_rule('/api/topology', 'topology', self.get_topology)
        self.app.add_url_rule('/api/transactions', 'transactions', self.get_transactions)

    def get_topology(self):
        nodes = [{
            'id': self.community.my_peer.mid.hex(),
            'label': self.community.my_peer.mid.hex()[:6],
            'color': 'green'
        }]
        
        links = []
        
        # Add peers and links to the topology
        for peer in self.community.get_peers():
            peer_id = peer.mid.hex()
            nodes.append({
                'id': peer_id,
                'label': peer_id[:6],
                'color': 'blue'
            })
            links.append({
                'source': self.community.my_peer.mid.hex(),
                'target': peer_id,
                'value': 5
            })
            
        return jsonify({'nodes': nodes, 'links': links})
    
    def get_transactions(self):
        return jsonify({'transactions': self.community.transactions[-10:]})
    
    def get_index(self):
        return render_template("index.html")

    def start(self):
        """Run the Flask server on the main thread"""
        self.app.run(host='0.0.0.0', port=self.port)
        print(f"Flask visualizer running on http://localhost:{self.port}")
