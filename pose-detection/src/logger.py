import csv
import os
from datetime import datetime

class TelemetryLogger:
    """Logs raw kinematic data per frame and exports to CSV for external biomechanical modeling."""
    def __init__(self, patient_id="PT-001", output_dir="data/sessions"):
        self.patient_id = patient_id
        self.output_dir = output_dir
        self.frames = []
        os.makedirs(self.output_dir, exist_ok=True)
        
    def log_frame(self, timestamp_ms, world_coords, angles, squat_metrics):
        row = {
            "timestamp_ms": timestamp_ms,
        }
        
        # Flatten 3D world coordinates (x, y, z in meters)
        if world_coords:
            for joint, coords in world_coords.items():
                if coords:
                    row[f"{joint}_x"] = round(coords[0], 5)
                    row[f"{joint}_y"] = round(coords[1], 5)
                    row[f"{joint}_z"] = round(coords[2], 5)
                else:
                    row[f"{joint}_x"] = ""
                    row[f"{joint}_y"] = ""
                    row[f"{joint}_z"] = ""
                    
        # Log joint angles
        if angles:
            for angle_name, value in angles.items():
                row[angle_name] = value
                
        # Log real-time state metrics
        if squat_metrics:
            for k, v in squat_metrics.items():
                row[k] = v
                
        self.frames.append(row)
        
    def save(self):
        """Saves the recorded session to a CSV file and returns the filepath."""
        if not self.frames:
            return None
            
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"session_{self.patient_id}_{timestamp_str}.csv"
        filepath = os.path.join(self.output_dir, filename)
        
        # Extract all unique keys for header
        headers = set()
        for frame in self.frames:
            headers.update(frame.keys())
            
        # Ensure timestamp is first, then group coords and metrics logically
        headers = ["timestamp_ms"] + sorted([h for h in headers if h != "timestamp_ms"])
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(self.frames)
            
        return filepath
