import pandas as pd
import numpy as np
from scipy.interpolate import pchip_interpolate
from scipy.signal import butter, filtfilt
import os

class KinematicFilter:
    """Applies biomechanical signal processing to raw kinematic CSV data."""
    
    def __init__(self, fps=30.0, cutoff_freq=6.0, max_velocity_m_s=5.0):
        self.fps = fps
        self.cutoff_freq = cutoff_freq
        self.max_velocity_m_s = max_velocity_m_s

    def _velocity_outlier_rejection(self, series, timestamps_ms):
        """Removes sudden impossible spikes right before tracking drops."""
        # Calculate time diffs in seconds
        dt = timestamps_ms.diff() / 1000.0
        # Calculate velocity
        velocity = series.diff() / dt
        
        # Where velocity exceeds anatomical limits, set the original value to NaN
        outlier_mask = velocity.abs() > self.max_velocity_m_s
        
        cleaned_series = series.copy()
        # Also remove the point before the spike, as MediaPipe often drags it
        shifted_mask = outlier_mask.shift(-1).fillna(False)
        
        cleaned_series[outlier_mask | shifted_mask] = np.nan
        return cleaned_series

    def _apply_pchip(self, series):
        """Applies Piecewise Cubic Hermite Interpolating Polynomial to preserve shape and prevent overshoots."""
        # Find valid indices and values
        valid_mask = series.notna()
        if valid_mask.sum() < 4:  # PCHIP needs at least 4 points
            return series.interpolate(method='linear') # fallback
            
        x_valid = valid_mask.to_numpy().nonzero()[0]
        y_valid = series[valid_mask].to_numpy()
        
        x_all = np.arange(len(series))
        
        try:
            # PCHIP strictly respects monotonic local shapes
            y_interp = pchip_interpolate(x_valid, y_valid, x_all)
            return pd.Series(y_interp, index=series.index)
        except Exception as e:
            # Fallback to linear if math fails at boundaries
            return series.interpolate(method='linear')

    def _apply_butterworth(self, series):
        """Zero-lag 4th-order Butterworth low-pass filter (OpenSim standard)."""
        nyquist = 0.5 * self.fps
        normal_cutoff = self.cutoff_freq / nyquist
        
        # Don't filter if there are NaNs left or too few points
        if series.isna().any() or len(series) < 15:
            return series
            
        b, a = butter(4, normal_cutoff, btype='low', analog=False)
        
        # filtfilt applies the filter forward and backward for zero phase lag
        filtered_data = filtfilt(b, a, series)
        return pd.Series(filtered_data, index=series.index)

    def process_session_csv(self, input_filepath):
        """Reads raw CSV, applies the 3-step kinematic filter to all coordinate columns, and exports a clean CSV."""
        if not os.path.exists(input_filepath):
            return None
            
        df = pd.read_csv(input_filepath)
        
        # Identify coordinate columns (e.g., l_knee_x, r_hip_z)
        coord_cols = [c for c in df.columns if c.endswith(('_x', '_y', '_z'))]
        
        if 'timestamp_ms' not in df.columns or len(coord_cols) == 0:
            return input_filepath
            
        timestamps = df['timestamp_ms']
        
        for col in coord_cols:
            # Convert to numeric, coercing empty strings to NaN
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Step 1: Velocity Outlier Rejection
            cleaned = self._velocity_outlier_rejection(df[col], timestamps)
            
            # Step 2: PCHIP Interpolation (fill all NaNs)
            interpolated = self._apply_pchip(cleaned)
            
            # Step 3: Zero-lag Butterworth Low-pass Filter
            smoothed = self._apply_butterworth(interpolated)
            
            df[col] = smoothed.round(5)

        # Generate output filename
        dir_name = os.path.dirname(input_filepath)
        base_name = os.path.basename(input_filepath)
        output_name = "filtered_" + base_name
        output_filepath = os.path.join(dir_name, output_name)
        
        df.to_csv(output_filepath, index=False)
        return output_filepath
