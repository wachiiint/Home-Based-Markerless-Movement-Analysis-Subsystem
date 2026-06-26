# src/analytics.py
import math
import numpy as np

def calculate_2d_angle(a, b, c):
    try:
        radians = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(a[1] - b[1], a[0] - b[0])
        angle = abs(radians * 180.0 / math.pi)
        if angle > 180.0:
            angle = 360.0 - angle
        return round(angle, 2)
    except Exception:
        return 0.0

def calculate_symmetry_index(left_val, right_val):
    if (left_val + right_val) == 0: return 0.0
    return round((abs(left_val - right_val) / (0.5 * (left_val + right_val))) * 100, 2)

def calculate_3d_angle(a, b, c):
    """
    Calculates the 3D angle (in degrees) at joint b given three 3D points a, b, c.
    Each point should be a sequence of 3 floats (x, y, z).
    """
    try:
        vec_ba = np.array(a) - np.array(b)
        vec_bc = np.array(c) - np.array(b)
        
        norm_ba = np.linalg.norm(vec_ba)
        norm_bc = np.linalg.norm(vec_bc)
        
        if norm_ba == 0 or norm_bc == 0:
            return 0.0
            
        cosine_angle = np.dot(vec_ba, vec_bc) / (norm_ba * norm_bc)
        cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
        
        angle = np.arccos(cosine_angle)
        return round(np.degrees(angle), 2)
    except Exception:
        return 0.0

class ClinicalTrackingProcessor:
    """Handles noise filtering and landmark memory retention during temporary occlusion."""
    def __init__(self, alpha=0.4, max_missing_frames=6):
        self.alpha = alpha
        self.max_missing_frames = max_missing_frames
        self.history = {} # Stores {'joint_id': (filtered_x, filtered_y)}
        self.missing_counters = {} # Tracks how many frames a joint has been missing

    def process_landmark(self, joint_id, current_coords, is_detected):
        """Applies EMA smoothing and holds the last position if tracking is dropped briefly."""
        if is_detected and current_coords is not None:
            self.missing_counters[joint_id] = 0
            curr_x, curr_y = current_coords
            
            if joint_id not in self.history:
                self.history[joint_id] = (curr_x, curr_y)
                return (curr_x, curr_y)
            
            # Apply EMA formula
            prev_x, prev_y = self.history[joint_id]
            smooth_x = self.alpha * curr_x + (1 - self.alpha) * prev_x
            smooth_y = self.alpha * curr_y + (1 - self.alpha) * prev_y
            
            self.history[joint_id] = (smooth_x, smooth_y)
            return (smooth_x, smooth_y)
        
        else:
            # Drop tracking fallback: check if we can borrow from memory
            if joint_id in self.history:
                self.missing_counters[joint_id] = self.missing_counters.get(joint_id, 0) + 1
                if self.missing_counters[joint_id] <= self.max_missing_frames:
                    # Return last known position
                    return self.history[joint_id]
            
            # Completely lost
            return None

def calculate_valgus_index(hip, knee, ankle, is_left_leg=True):
    """
    Measures the horizontal deviation of the knee center relative to the hip-ankle vector in the frontal plane (X-Y).
    Returns a signed distance. Positive means outward (varus), negative means inward (valgus).
    Assumes standard image coordinates (X right, Y down).
    """
    try:
        # Frontal plane points
        hx, hy = hip[0], hip[1]
        kx, ky = knee[0], knee[1]
        ax, ay = ankle[0], ankle[1]
        
        # Line from hip to ankle
        dx = ax - hx
        dy = ay - hy
        
        # Length of hip-ankle line
        length = math.hypot(dx, dy)
        if length == 0:
            return 0.0
            
        # Distance from point to line in 2D
        # cross_prod = dx * (ky - hy) - dy * (kx - hx)
        # However, to explicitly check inward/outward:
        # Let's project knee onto the horizontal axis perpendicular to the vertical-ish leg.
        # A simpler approach: just the horizontal distance from the knee to the hip-ankle line segment.
        # Line eq: (x - hx)/(ax - hx) = (y - hy)/(ay - hy) => x = hx + (y - hy) * dx / dy
        if dy == 0:
            return 0.0
            
        expected_kx = hx + (ky - hy) * (dx / dy)
        deviation = kx - expected_kx
        
        # For the left leg (patient's left, usually on the right side of the image if facing camera)
        # Wait, if patient faces camera:
        # Patient Left Leg: x-coord is larger (further right). Inward (valgus) means knee moves left -> smaller x -> negative deviation.
        # Patient Right Leg: x-coord is smaller (further left). Inward (valgus) means knee moves right -> larger x -> positive deviation.
        if is_left_leg:
            # If deviation is negative, it's moving left (inward towards center)
            return deviation  # negative = valgus
        else:
            # If deviation is positive, it's moving right (inward towards center)
            return -deviation # negative = valgus
    except Exception:
        return 0.0

class SquatAnalyzer:
    """Tracks squat repetitions, depth metrics, and knee valgus/varus."""
    def __init__(self, valgus_threshold=-0.05):
        self.reps = 0
        self.is_squatting = False
        self.standing_hip_height_l = None
        self.standing_hip_height_r = None
        
        # Metrics for current rep (reset each rep)
        self.current_depth_ratio = 1.0
        self.min_depth_ratio = 1.0  # deepest point in the CURRENT rep
        self.max_knee_angle_l = 0.0  # max knee flexion angle in CURRENT rep
        self.max_knee_angle_r = 0.0
        
        self.valgus_threshold = valgus_threshold
        self.valgus_flag_l = False
        self.valgus_flag_r = False
        
        # Per-rep history for telemetry
        self.rep_history = []  # list of dicts, one per completed rep

    def reset(self):
        self.__init__(self.valgus_threshold)

    def _reset_rep_metrics(self):
        """Resets per-rep tracking metrics at the start of a new squat."""
        self.min_depth_ratio = self.current_depth_ratio
        self.max_knee_angle_l = 0.0
        self.max_knee_angle_r = 0.0

    def process_frame(self, world_coords):
        """
        Processes a single frame of 3D world coordinates.
        world_coords is a dict mapping joint names to (x, y, z).
        Returns a metrics dict or None if coordinates are unavailable.
        """
        if not world_coords:
            return None
            
        l_hip = world_coords.get("l_hip")
        r_hip = world_coords.get("r_hip")
        l_knee = world_coords.get("l_knee")
        r_knee = world_coords.get("r_knee")
        l_ankle = world_coords.get("l_ankle")
        r_ankle = world_coords.get("r_ankle")
        
        # Ensure we have all necessary points
        if not all([l_hip, r_hip, l_knee, r_knee, l_ankle, r_ankle]):
            return None
            
        # 3D Euclidean distance between hip and ankle (camera-angle invariant depth proxy)
        curr_dist_l = math.sqrt(
            (l_hip[0]-l_ankle[0])**2 + (l_hip[1]-l_ankle[1])**2 + (l_hip[2]-l_ankle[2])**2
        )
        curr_dist_r = math.sqrt(
            (r_hip[0]-r_ankle[0])**2 + (r_hip[1]-r_ankle[1])**2 + (r_hip[2]-r_ankle[2])**2
        )
        
        # Initialize standing height baseline on first valid frame
        if self.standing_hip_height_l is None or self.standing_hip_height_r is None:
            self.standing_hip_height_l = curr_dist_l
            self.standing_hip_height_r = curr_dist_r
            return None
            
        # Update standing height via EMA if patient stands taller than recorded baseline
        # (Handles initial uncertainty before patient fully straightens up)
        if curr_dist_l > self.standing_hip_height_l:
            self.standing_hip_height_l = 0.9 * self.standing_hip_height_l + 0.1 * curr_dist_l
        if curr_dist_r > self.standing_hip_height_r:
            self.standing_hip_height_r = 0.9 * self.standing_hip_height_r + 0.1 * curr_dist_r
            
        # Depth ratio: 1.0 = standing, <1.0 = squatting, ~0.55 = deep squat
        ratio_l = curr_dist_l / self.standing_hip_height_l if self.standing_hip_height_l > 0 else 1.0
        ratio_r = curr_dist_r / self.standing_hip_height_r if self.standing_hip_height_r > 0 else 1.0
        avg_ratio = (ratio_l + ratio_r) / 2.0
        self.current_depth_ratio = avg_ratio
        
        # 3D Knee Angles (Hip-Knee-Ankle) using world landmarks
        knee_angle_l = calculate_3d_angle(l_hip, l_knee, l_ankle)
        knee_angle_r = calculate_3d_angle(r_hip, r_knee, r_ankle)
        
        # Valgus Index (signed horizontal deviation in meters)
        valgus_idx_l = calculate_valgus_index(l_hip, l_knee, l_ankle, is_left_leg=True)
        valgus_idx_r = calculate_valgus_index(r_hip, r_knee, r_ankle, is_left_leg=False)
        self.valgus_flag_l = valgus_idx_l < self.valgus_threshold
        self.valgus_flag_r = valgus_idx_r < self.valgus_threshold
        
        # State machine for squat rep counting
        # Squat starts when depth drops below 0.80, completes when it rises back above 0.92
        if not self.is_squatting and avg_ratio < 0.80:
            self.is_squatting = True
            self._reset_rep_metrics()  # Fresh tracking for this new rep
        
        if self.is_squatting:
            # Track deepest point of this rep
            if avg_ratio < self.min_depth_ratio:
                self.min_depth_ratio = avg_ratio
            # Track maximum knee flexion of this rep (smaller angle = more flexed)
            # We track the SMALLEST angle as maximum flexion
            if knee_angle_l > 0:
                self.max_knee_angle_l = max(self.max_knee_angle_l, 180.0 - knee_angle_l)
            if knee_angle_r > 0:
                self.max_knee_angle_r = max(self.max_knee_angle_r, 180.0 - knee_angle_r)
                
            if avg_ratio > 0.92:
                # Rep completed: save rep summary to history
                self.rep_history.append({
                    "rep": self.reps + 1,
                    "min_depth": round(self.min_depth_ratio, 3),
                    "max_flexion_l": round(self.max_knee_angle_l, 1),
                    "max_flexion_r": round(self.max_knee_angle_r, 1),
                    "valgus_l": self.valgus_flag_l,
                    "valgus_r": self.valgus_flag_r,
                })
                self.reps += 1
                self.is_squatting = False
                
        return {
            "reps": self.reps,
            "is_squatting": self.is_squatting,
            "current_depth": round(self.current_depth_ratio, 3),
            "min_depth_this_rep": round(self.min_depth_ratio, 3),
            "knee_angle_l": round(knee_angle_l, 1),
            "knee_angle_r": round(knee_angle_r, 1),
            "max_flexion_l": round(self.max_knee_angle_l, 1),
            "max_flexion_r": round(self.max_knee_angle_r, 1),
            "valgus_l": self.valgus_flag_l,
            "valgus_r": self.valgus_flag_r,
            "valgus_idx_l": round(valgus_idx_l, 3),
            "valgus_idx_r": round(valgus_idx_r, 3)
        }

class GaitAnalyzer:
    """Tracks walking steps, stance/swing phases, and leg symmetry index."""
    def __init__(self, step_threshold=0.25, stance_threshold=0.15):
        self.step_count = 0
        self.current_max_dist = 0.0
        self.in_swing = False
        self.step_threshold = step_threshold
        self.stance_threshold = stance_threshold
        
        self.l_step_lengths = []
        self.r_step_lengths = []
        
        self.symmetry_index = 0.0
        self.is_asymmetric = False
        
        self.current_leading_leg = None

    def reset(self):
        self.__init__(self.step_threshold, self.stance_threshold)

    def process_frame(self, world_coords):
        if not world_coords: return None
        l_hip = world_coords.get("l_hip")
        r_hip = world_coords.get("r_hip")
        l_ankle = world_coords.get("l_ankle")
        r_ankle = world_coords.get("r_ankle")
        
        if not all([l_hip, r_hip, l_ankle, r_ankle]):
            return None
            
        # Horizontal inter-ankle distance (proxy for stride spread)
        dist = math.hypot(l_ankle[0] - r_ankle[0], l_ankle[2] - r_ankle[2])
        
        # Determine leading leg using 3D patient-relative forward axis
        lateral = np.array(r_hip) - np.array(l_hip)
        vertical = np.array([0, 1, 0]) # MediaPipe Y is down
        forward = np.cross(lateral, vertical)
        norm = np.linalg.norm(forward)
        
        leading_leg = "L"
        if norm > 0:
            forward = forward / norm
            pelvis = (np.array(l_hip) + np.array(r_hip)) / 2.0
            l_ext = np.dot(np.array(l_ankle) - pelvis, forward)
            r_ext = np.dot(np.array(r_ankle) - pelvis, forward)
            leading_leg = "L" if l_ext > r_ext else "R"
            
        # Gait State Machine
        if dist > self.step_threshold:
            self.in_swing = True
            if dist > self.current_max_dist:
                self.current_max_dist = dist
                self.current_leading_leg = leading_leg
        elif dist < self.stance_threshold and self.in_swing:
            # Step completed (Mid-stance crossover)
            if self.current_max_dist > self.step_threshold: 
                self.step_count += 1
                if self.current_leading_leg == "L":
                    self.l_step_lengths.append(self.current_max_dist)
                else:
                    self.r_step_lengths.append(self.current_max_dist)
                    
                # Update Symmetry Index (SI)
                if len(self.l_step_lengths) > 0 and len(self.r_step_lengths) > 0:
                    avg_l = sum(self.l_step_lengths) / len(self.l_step_lengths)
                    avg_r = sum(self.r_step_lengths) / len(self.r_step_lengths)
                    self.symmetry_index = calculate_symmetry_index(avg_l, avg_r)
                    self.is_asymmetric = self.symmetry_index > 10.0 # >10% flags asymmetry
                    
            self.in_swing = False
            self.current_max_dist = 0.0
            
        return {
            "step_count": self.step_count,
            "current_step_dist": round(dist, 2),
            "symmetry_index": self.symmetry_index,
            "is_asymmetric": self.is_asymmetric,
            "phase": "SWING" if self.in_swing else "STANCE"
        }