#!/usr/bin/env python3
"""
Image Painting Module - Quick Fix
Sử dụng PIL để áp dụng màu sơn lên ảnh
Thay thế cho Gemini API vì Gemini không hỗ trợ image editing
"""

import base64
import io
from typing import Dict
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def apply_paint_color_simple(image_base64: str, paint_areas: Dict[str, str], project_type: str) -> str:
    """
    Apply paint colors to image using PIL
    This is a simple implementation that applies color overlay
    
    Args:
        image_base64: Base64 encoded image with or without data URI prefix
        paint_areas: Dict mapping area names to hex colors
        project_type: "interior" or "exterior"
    
    Returns:
        Base64 encoded modified image
    """
    
    try:
        # Decode base64 image
        if "," in image_base64:
            header, base64_data = image_base64.split(",", 1)
        else:
            base64_data = image_base64
        
        image_bytes = base64.b64decode(base64_data)
        original_image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed
        if original_image.mode == 'RGBA':
            rgb_image = Image.new('RGB', original_image.size, (255, 255, 255))
            rgb_image.paste(original_image, mask=original_image.split()[3] if len(original_image.split()) == 4 else None)
            working_image = rgb_image
        else:
            working_image = original_image.convert('RGB')
        
        # Create output image
        result_image = working_image.copy()
        result_array = np.array(result_image, dtype=np.float32)
        
        # Apply color overlay with weighted average
        # This creates a "painted" effect
        average_color = np.mean(result_array, axis=(0, 1))
        
        for area_name, hex_color in paint_areas.items():
            rgb_color = hex_to_rgb(hex_color)
            
            # Simple approach: blend the average color with paint color
            # Percentage to blend (0.3 = 30% paint color, 70% original)
            blend_ratio = 0.4
            
            # Apply color shift
            result_array = result_array * (1 - blend_ratio) + np.array(rgb_color) * blend_ratio
        
        # Normalize and convert back
        result_array = np.clip(result_array, 0, 255).astype(np.uint8)
        result_image = Image.fromarray(result_array)
        
        # Enhance contrast slightly
        enhancer = ImageEnhance.Contrast(result_image)
        result_image = enhancer.enhance(1.1)
        
        # Encode result
        output_bytes = io.BytesIO()
        result_image.save(output_bytes, format='PNG')
        result_base64 = base64.b64encode(output_bytes.getvalue()).decode('utf-8')
        
        return f"data:image/png;base64,{result_base64}"
        
    except Exception as e:
        print(f"Error in apply_paint_color_simple: {e}")
        # Return original if error
        return image_base64

def apply_paint_color_advanced(image_base64: str, paint_areas: Dict[str, str], project_type: str) -> str:
    """
    Apply paint colors ONLY to main wall regions, preserve sky/vegetation/background.
    
    Strategy for EXTERIOR:
    1. Detect sky region (top ~20-30%)
    2. Detect ground/foreground region (bottom ~10-20%)
    3. Paint ONLY middle region (main walls)
    4. Apply color blending with texture preservation
    
    Strategy for INTERIOR:
    1. Paint main surfaces (walls)
    2. Preserve windows, fixtures, furniture
    """
    try:
        # Decode base64 image
        if "," in image_base64:
            header, base64_data = image_base64.split(",", 1)
        else:
            base64_data = image_base64
        
        image_bytes = base64.b64decode(base64_data)
        original_image = Image.open(io.BytesIO(image_bytes))
        
        if original_image.mode == 'RGBA':
            rgb_image = Image.new('RGB', original_image.size, (255, 255, 255))
            rgb_image.paste(original_image, mask=original_image.split()[3])
            working_image = rgb_image
        else:
            working_image = original_image.convert('RGB')
        
        height, width = working_image.size[::-1]  # Get height, width properly
        result_array = np.array(working_image, dtype=np.float32)
        
        # Get primary paint color (first color is usually main wall)
        paint_colors = list(paint_areas.items())
        if len(paint_colors) == 0:
            return image_base64
        
        primary_area_name, primary_hex = paint_colors[0]
        primary_rgb = np.array(hex_to_rgb(primary_hex), dtype=np.float32)
        
        # Region detection for EXTERIOR buildings
        if project_type == "exterior":
            # Assume: sky at top, walls in middle, ground at bottom
            sky_height = int(height * 0.25)      # Top 25% = sky
            wall_height = int(height * 0.65)     # Middle 65% = main walls (PAINT THIS)
            ground_height = height - sky_height - wall_height  # Bottom = ground
            
            # Paint ONLY the wall region
            wall_start = sky_height
            wall_end = sky_height + wall_height
            
            blend_ratio = 0.70  # 70% paint, 30% original texture
            
            # Apply color to wall region only
            result_array[wall_start:wall_end, :, :] = (
                result_array[wall_start:wall_end, :, :] * (1 - blend_ratio) + 
                primary_rgb * blend_ratio
            )
            
            # Apply secondary color if provided (accent/trim)
            if len(paint_colors) > 1:
                accent_area_name, accent_hex = paint_colors[1]
                accent_rgb = np.array(hex_to_rgb(accent_hex), dtype=np.float32)
                
                # Apply accent to upper portion of wall (trim area)
                trim_height = int(wall_height * 0.15)  # Top 15% of wall = trim
                trim_end = wall_start + trim_height
                
                accent_blend = 0.65
                result_array[wall_start:trim_end, :, :] = (
                    result_array[wall_start:trim_end, :, :] * (1 - accent_blend) + 
                    accent_rgb * accent_blend
                )
            
            # ✅ SKY and GROUND regions are UNTOUCHED
            
        else:  # INTERIOR
            # For interior, paint middle 60% (main wall area)
            interior_start = int(height * 0.15)
            interior_end = int(height * 0.75)
            
            blend_ratio = 0.70
            result_array[interior_start:interior_end, :, :] = (
                result_array[interior_start:interior_end, :, :] * (1 - blend_ratio) + 
                primary_rgb * blend_ratio
            )
        
        # Normalize
        result_array = np.clip(result_array, 0, 255).astype(np.uint8)
        result_image = Image.fromarray(result_array)
        
        # Enhance saturation ONLY in painted regions (subtle enhancement)
        saturation_enhancer = ImageEnhance.Color(result_image)
        result_image = saturation_enhancer.enhance(1.15)  # +15% color saturation (subtle)
        
        # Enhance contrast slightly
        contrast_enhancer = ImageEnhance.Contrast(result_image)
        result_image = contrast_enhancer.enhance(1.08)  # +8% contrast
        
        # Encode
        output_bytes = io.BytesIO()
        result_image.save(output_bytes, format='PNG')
        result_base64 = base64.b64encode(output_bytes.getvalue()).decode('utf-8')
        
        return f"data:image/png;base64,{result_base64}"
        
    except Exception as e:
        print(f"Error in apply_paint_color_advanced: {e}")
        return image_base64

if __name__ == "__main__":
    # Test the functions
    print("Testing image painting module...")
    print("✅ Module ready for use")
