#!/usr/bin/env python3
"""
YOLO Detector Module for Architectural Analysis
Detects wall, window, door, ceiling areas in architectural images
Uses YOLOv8 with GPU acceleration (RX 6550M) or CPU fallback
"""

import os
import logging
import torch
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from ultralytics import YOLO
from PIL import Image
import cv2

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ArchitectureDetector:
    """
    YOLO-based detector for architectural elements.
    Automatically selects GPU (RX 6550M) or falls back to CPU.
    """
    
    # YOLO class mappings for architectural elements
    ARCHITECTURE_CLASSES = {
        "wall": 0,
        "window": 1,
        "door": 2,
        "ceiling": 3,
        "column": 4,
        "trim": 5,
        "roof": 6,
    }
    
    # Reverse mapping
    CLASS_NAMES = {v: k for k, v in ARCHITECTURE_CLASSES.items()}
    
    def __init__(self, model_path: str = "models/yolov8s.pt", use_gpu: bool = True):
        """
        Initialize YOLO detector with automatic device selection.
        
        Args:
            model_path (str): Path to YOLOv8 model (default: yolov8s.pt)
            use_gpu (bool): Try to use GPU if available (default: True)
        """
        self.model_path = model_path
        self.device = self._select_device(use_gpu)
        self.model = self._load_model()
        self._log_device_info()
    
    def _select_device(self, use_gpu: bool) -> str:
        """Select appropriate device (GPU or CPU)."""
        if use_gpu and torch.cuda.is_available():
            return "cuda"
        elif use_gpu and torch.backends.mps.is_available():  # macOS GPU
            return "mps"
        else:
            return "cpu"
    
    def _load_model(self) -> YOLO:
        """Load YOLO model."""
        try:
            model = YOLO(self.model_path)
            model.to(self.device)
            logger.info(f"✅ Loaded YOLO model from {self.model_path}")
            return model
        except Exception as e:
            logger.error(f"❌ Failed to load YOLO model: {e}")
            raise
    
    def _log_device_info(self):
        """Log device information."""
        logger.info(f"🚀 Using device: {self.device}")
        
        if self.device == "cuda":
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info(f"   GPU: {gpu_name}")
            logger.info(f"   Memory: {gpu_memory:.1f}GB")
        elif self.device == "cpu":
            logger.info(f"   CPU: {torch.get_num_threads()} threads available")
    
    def detect(
        self,
        image_source: Any,
        conf: float = 0.5,
        iou: float = 0.45,
        imgsz: int = 640
    ) -> List[Dict[str, Any]]:
        """
        Detect architectural areas in image.
        
        Args:
            image_source: Image path, PIL Image, or numpy array
            conf (float): Confidence threshold (0-1)
            iou (float): IoU threshold for NMS
            imgsz (int): Image size for inference
        
        Returns:
            List of detected areas with format compatible with PaintAI
        """
        try:
            # Run YOLO inference
            results = self.model.predict(
                image_source,
                conf=conf,
                iou=iou,
                imgsz=imgsz,
                device=self.device,
                verbose=False,
                half=(self.device == "cuda")  # Use FP16 on GPU for speed
            )
            
            # Parse results
            detected_areas = self._parse_results(results)
            logger.info(f"✅ Detected {len(detected_areas)} areas")
            
            return detected_areas
            
        except Exception as e:
            logger.error(f"❌ Detection failed: {e}")
            return []
    
    def _parse_results(self, results) -> List[Dict[str, Any]]:
        """
        Parse YOLO results into PaintAI format.
        
        Returns:
            List of detected areas with:
            - area_id: Unique identifier
            - type: Architecture type (wall, window, door, etc.)
            - confidence: Detection confidence (0-1)
            - box_2d: Normalized bounding box [x1, y1, x2, y2]
            - polygon_2d: Optional segmentation polygon
            - source: "yolo"
        """
        detected_areas = []
        
        for result in results:
            image_height, image_width = result.orig_shape
            
            # Process bounding boxes
            if result.boxes is not None:
                boxes = result.boxes.xyxy.cpu().numpy()
                confs = result.boxes.conf.cpu().numpy()
                classes = result.boxes.cls.cpu().numpy()
                
                for idx, (box, conf, cls) in enumerate(zip(boxes, confs, classes)):
                    x1, y1, x2, y2 = box
                    
                    # Normalize coordinates to 0-1000 range (compatible with metadata)
                    bbox_normalized = [
                        float(x1 / image_width * 1000),
                        float(y1 / image_height * 1000),
                        float(x2 / image_width * 1000),
                        float(y2 / image_height * 1000)
                    ]
                    
                    # Get class name
                    class_id = int(cls)
                    class_name = self.CLASS_NAMES.get(class_id, "unknown")
                    
                    area = {
                        "area_id": f"yolo-{class_name}-{idx}",
                        "type": class_name,
                        "confidence": float(conf),
                        "box_2d": bbox_normalized,
                        "polygon_2d": None,
                        "source": "yolo"
                    }
                    
                    detected_areas.append(area)
            
            # Process masks (if available from segment models)
            if hasattr(result, 'masks') and result.masks is not None:
                masks = result.masks.xy
                
                for idx, mask in enumerate(masks):
                    if idx < len(detected_areas):
                        # Normalize polygon coordinates
                        polygon_normalized = [
                            [float(p[0] / image_width * 1000), 
                             float(p[1] / image_height * 1000)]
                            for p in mask
                        ]
                        detected_areas[idx]["polygon_2d"] = polygon_normalized
        
        return detected_areas
    
    def detect_from_base64(
        self,
        image_base64: str,
        conf: float = 0.5
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Detect areas from base64 encoded image (FastAPI integration).
        
        Args:
            image_base64 (str): Base64 encoded image string
            conf (float): Confidence threshold
        
        Returns:
            Tuple of (detected_areas, success)
        """
        try:
            import base64
            from io import BytesIO
            
            # Decode base64
            image_data = base64.b64decode(image_base64)
            image = Image.open(BytesIO(image_data))
            
            # Convert to numpy for YOLO
            image_array = np.array(image)
            
            # Detect
            detected_areas = self.detect(image_array, conf=conf)
            
            return detected_areas, True
            
        except Exception as e:
            logger.error(f"❌ Base64 detection failed: {e}")
            return [], False
    
    def benchmark(self, image_path: str, num_runs: int = 5) -> Dict[str, float]:
        """
        Benchmark detection speed on given image.
        
        Args:
            image_path (str): Path to test image
            num_runs (int): Number of inference runs
        
        Returns:
            Dictionary with timing statistics
        """
        import time
        
        times = []
        
        for _ in range(num_runs):
            start = time.time()
            self.detect(image_path)
            elapsed = time.time() - start
            times.append(elapsed)
        
        return {
            "device": self.device,
            "avg_time_ms": np.mean(times) * 1000,
            "min_time_ms": np.min(times) * 1000,
            "max_time_ms": np.max(times) * 1000,
            "std_time_ms": np.std(times) * 1000,
        }


def get_detector(use_gpu: bool = True) -> ArchitectureDetector:
    """Factory function to get/create detector instance."""
    model_path = os.environ.get("YOLO_MODEL_PATH", "models/yolov8s.pt")
    return ArchitectureDetector(model_path=model_path, use_gpu=use_gpu)


if __name__ == "__main__":
    # Test the detector
    import sys
    
    # Initialize detector
    detector = get_detector(use_gpu=True)
    
    # If image path provided, test detection
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print(f"\n📸 Testing detection on: {image_path}")
        
        areas = detector.detect(image_path)
        print(f"\n✅ Detected {len(areas)} areas:")
        for area in areas:
            print(f"  - {area['type']}: confidence={area['confidence']:.2f}")
        
        # Benchmark
        if len(sys.argv) > 2 and sys.argv[2] == "--benchmark":
            print(f"\n⏱️  Running benchmark...")
            stats = detector.benchmark(image_path, num_runs=5)
            print(f"   Device: {stats['device']}")
            print(f"   Avg: {stats['avg_time_ms']:.1f}ms")
            print(f"   Min: {stats['min_time_ms']:.1f}ms")
            print(f"   Max: {stats['max_time_ms']:.1f}ms")
    else:
        print("Usage: python yolo_detector.py <image_path> [--benchmark]")
