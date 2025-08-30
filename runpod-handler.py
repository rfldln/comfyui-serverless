#!/usr/bin/env python3
"""
RunPod Serverless Handler for Text-to-Image Generation
This script should be deployed to your RunPod serverless pod with network volume access.

Network Volume Structure:
/runpod-volume/
├── models/
│   ├── checkpoints/
│   │   └── flux1-dev.safetensors
│   ├── clip/
│   │   ├── t5xxl_fp16.safetensors
│   │   └── clip_l.safetensors
│   ├── vae/
│   │   └── ae.safetensors
│   └── loras/
│       └── your_lora_models.safetensors
└── ComfyUI/
    └── (your ComfyUI installation)
"""

import runpod
import json
import os
import sys
import uuid
import base64
import requests
from pathlib import Path
import subprocess
import time

# Add ComfyUI to Python path if installed in network volume
NETWORK_VOLUME = "/runpod-volume"
COMFYUI_PATH = os.path.join(NETWORK_VOLUME, "ComfyUI")
if os.path.exists(COMFYUI_PATH):
    sys.path.insert(0, COMFYUI_PATH)

def setup_comfyui():
    """Initialize ComfyUI from network volume"""
    try:
        # Set up model paths to point to network volume
        os.environ['COMFYUI_MODEL_PATH'] = os.path.join(NETWORK_VOLUME, "models")
        
        # Import ComfyUI modules
        from execution import PromptExecutor
        from server import PromptServer
        import nodes
        import comfy.model_management as mm
        
        print("✅ ComfyUI initialized from network volume")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize ComfyUI: {str(e)}")
        return False

def validate_models():
    """Check if required models exist in network volume"""
    models_path = os.path.join(NETWORK_VOLUME, "models")
    required_models = {
        "checkpoint": os.path.join(models_path, "checkpoints/flux1-dev.safetensors"),
        "vae": os.path.join(models_path, "vae/ae.safetensors"),
        "clip1": os.path.join(models_path, "clip/t5xxl_fp16.safetensors"),
        "clip2": os.path.join(models_path, "clip/clip_l.safetensors"),
    }
    
    missing_models = []
    for model_type, path in required_models.items():
        if not os.path.exists(path):
            missing_models.append(f"{model_type}: {path}")
    
    if missing_models:
        print("❌ Missing models:")
        for missing in missing_models:
            print(f"   {missing}")
        return False
    
    print("✅ All required models found in network volume")
    return True

def execute_comfyui_workflow(workflow, job_id):
    """Execute ComfyUI workflow and return results"""
    try:
        print(f"🎨 Executing workflow for job: {job_id}")
        
        # Here you would integrate with your ComfyUI execution logic
        # This is a simplified example - adjust based on your ComfyUI setup
        
        from execution import PromptExecutor
        import comfy.model_management as mm
        
        # Initialize executor
        executor = PromptExecutor()
        
        # Execute the workflow
        results = executor.execute(workflow, job_id)
        
        print(f"✅ Workflow execution completed for job: {job_id}")
        return results
        
    except Exception as e:
        print(f"❌ Workflow execution failed: {str(e)}")
        raise e

def convert_images_to_base64(image_paths):
    """Convert generated images to base64 for return"""
    base64_images = []
    
    for image_path in image_paths:
        try:
            with open(image_path, 'rb') as img_file:
                base64_data = base64.b64encode(img_file.read()).decode('utf-8')
                base64_images.append(base64_data)
                print(f"✅ Converted image to base64: {image_path}")
        except Exception as e:
            print(f"❌ Failed to convert image {image_path}: {str(e)}")
    
    return base64_images

def send_webhook(webhook_url, status, job_id, output=None, error=None):
    """Send status update to webhook URL"""
    if not webhook_url:
        return
        
    try:
        payload = {
            'job_id': job_id,
            'status': status,
            'timestamp': int(time.time())
        }
        
        if output:
            payload['output'] = output
        if error:
            payload['error'] = error
            
        response = requests.post(webhook_url, json=payload, timeout=10)
        print(f"📡 Webhook sent: {status} for job {job_id}")
        
    except Exception as e:
        print(f"⚠️ Failed to send webhook: {str(e)}")

def handler(event):
    """
    RunPod handler function
    Expected input format:
    {
        "job_id": "unique-job-id",
        "user_id": "clerk-user-id", 
        "workflow": {...}, // ComfyUI workflow JSON
        "params": {
            "prompt": "description",
            "width": 1024,
            "height": 1024,
            ...
        },
        "webhook_url": "https://yourapp.com/api/webhooks/..."
    }
    """
    
    try:
        print("🚀 RunPod Text-to-Image Handler Started")
        print(f"📥 Input: {json.dumps(event.get('input', {}), indent=2)}")
        
        # Extract input data
        input_data = event.get('input', {})
        job_id = input_data.get('job_id', str(uuid.uuid4()))
        user_id = input_data.get('user_id', 'unknown')
        workflow = input_data.get('workflow', {})
        params = input_data.get('params', {})
        webhook_url = input_data.get('webhook_url')
        
        print(f"🆔 Processing job: {job_id} for user: {user_id}")
        
        # Validate input
        if not workflow:
            error_msg = "Missing workflow in input"
            print(f"❌ {error_msg}")
            send_webhook(webhook_url, 'FAILED', job_id, error=error_msg)
            return {"error": error_msg}
            
        if not params.get('prompt'):
            error_msg = "Missing prompt in params"
            print(f"❌ {error_msg}")
            send_webhook(webhook_url, 'FAILED', job_id, error=error_msg)
            return {"error": error_msg}
        
        # Send initial webhook
        send_webhook(webhook_url, 'IN_PROGRESS', job_id)
        
        # Initialize ComfyUI if not already done
        if not setup_comfyui():
            error_msg = "Failed to initialize ComfyUI"
            send_webhook(webhook_url, 'FAILED', job_id, error=error_msg)
            return {"error": error_msg}
            
        # Validate models exist
        if not validate_models():
            error_msg = "Required models not found in network volume"
            send_webhook(webhook_url, 'FAILED', job_id, error=error_msg)
            return {"error": error_msg}
        
        print(f"🎯 Generating image with prompt: {params['prompt'][:100]}...")
        
        # Execute the workflow
        try:
            results = execute_comfyui_workflow(workflow, job_id)
            
            # Process results (this depends on your ComfyUI workflow structure)
            generated_images = []
            
            # Look for generated image files
            # Adjust this path based on your ComfyUI output configuration
            output_dir = os.path.join(COMFYUI_PATH, "output")
            
            # Find the most recent images with our job prefix
            import glob
            image_pattern = os.path.join(output_dir, f"runpod_generation*{job_id}*.png")
            image_files = glob.glob(image_pattern)
            
            if not image_files:
                # Fallback: look for any recent images
                image_pattern = os.path.join(output_dir, "*.png")
                all_images = glob.glob(image_pattern)
                # Sort by modification time and take the most recent
                all_images.sort(key=os.path.getmtime, reverse=True)
                image_files = all_images[:params.get('batch_size', 1)]
            
            if image_files:
                print(f"📸 Found {len(image_files)} generated images")
                
                # Convert to base64
                base64_images = convert_images_to_base64(image_files)
                
                # Prepare output
                output = {
                    'images': base64_images,
                    'job_id': job_id,
                    'prompt': params['prompt'],
                    'image_count': len(base64_images),
                    'generation_params': params
                }
                
                # Send success webhook
                send_webhook(webhook_url, 'COMPLETED', job_id, output=output)
                
                print(f"✅ Successfully generated {len(base64_images)} images for job {job_id}")
                return output
                
            else:
                error_msg = "No images generated"
                print(f"❌ {error_msg}")
                send_webhook(webhook_url, 'FAILED', job_id, error=error_msg)
                return {"error": error_msg}
                
        except Exception as workflow_error:
            error_msg = f"Workflow execution failed: {str(workflow_error)}"
            print(f"❌ {error_msg}")
            send_webhook(webhook_url, 'FAILED', job_id, error=error_msg)
            return {"error": error_msg}
            
    except Exception as e:
        error_msg = f"Handler error: {str(e)}"
        print(f"💥 {error_msg}")
        return {"error": error_msg}

# Initialize RunPod serverless
if __name__ == "__main__":
    print("🔥 Starting RunPod Text-to-Image Serverless Handler")
    print(f"📁 Network volume path: {NETWORK_VOLUME}")
    print(f"🖼️ ComfyUI path: {COMFYUI_PATH}")
    
    # Validate environment
    if not os.path.exists(NETWORK_VOLUME):
        print(f"⚠️ Warning: Network volume not found at {NETWORK_VOLUME}")
    
    # Start RunPod serverless
    runpod.serverless.start({"handler": handler})
