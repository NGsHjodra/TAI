from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO, emit
import threading

class FlaskVisualizerAll:
    def __init__(self, community, port=8080):
        self.community = community
        self.port = port
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app) 

        self.app.add_url_rule('/', 'all_nodes', self.get_all_nodes)
        self.app.add_url_rule('/api/all_topology', 'all_topology', self.get_all_topology)

        # For real-time updates via WebSocket
        self.socketio.on_event('get_update', self.send_updates)

    def get_all_topology(self):
        topology_data = {
            'nodes': list(self.community.known_topology.get('nodes', {}).values()),
            'links': self.community.known_topology.get('connections', [])
        }
        return jsonify(topology_data)
    
    def get_all_nodes(self):
        return render_template("all_nodes.html")

    def send_updates(self, message):
        updates = {
            'nodes': list(self.community.known_topology.get('nodes', {}).values()),
            'links': self.community.known_topology.get('connections', [])
        }
        emit('update', updates) 

    def start(self):
        """Run the Flask server with SocketIO"""
        # Start Flask and WebSocket in separate threads for non-blocking behavior
        threading.Thread(target=self.socketio.run, args=(self.app,), kwargs={'host': '0.0.0.0', 'port': self.port, 'allow_unsafe_werkzeug': True}).start()
        print(f"Flask visualizer all running on http://localhost:{self.port}")
