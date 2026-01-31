import runpod
from runpod.serverless.utils import rp_upload
import os
import websocket
import base64
import json
import uuid
import logging
import urllib.request
import urllib.parse
import binascii # Base64 에러 처리를 위해 import
import subprocess
import time
import shutil
# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


server_address = os.getenv('SERVER_ADDRESS', '127.0.0.1')
client_id = str(uuid.uuid4())
comfyui_input_dir = os.getenv('COMFYUI_INPUT_DIR', '/ComfyUI/input')
def to_nearest_multiple_of_16(value):
    """주어진 값을 가장 가까운 16의 배수로 보정, 최소 16 보장"""
    try:
        numeric_value = float(value)
    except Exception:
        raise Exception(f"width/height 값이 숫자가 아닙니다: {value}")
    adjusted = int(round(numeric_value / 16.0) * 16)
    if adjusted < 16:
        adjusted = 16
    return adjusted
def process_input(input_data, temp_dir, output_filename, input_type):
    """입력 데이터를 처리하여 ComfyUI input에 저장하고 파일명을 반환하는 함수"""
    if input_type == "path":
        # 경로인 경우 그대로 반환
        logger.info(f"📁 경로 입력 처리: {input_data}")
        return stage_image_to_comfyui_input(input_data, temp_dir, output_filename)
    elif input_type == "url":
        # URL인 경우 다운로드
        logger.info(f"🌐 URL 입력 처리: {input_data}")
        os.makedirs(comfyui_input_dir, exist_ok=True)
        file_path = os.path.abspath(os.path.join(comfyui_input_dir, f"{temp_dir}_{output_filename}"))
        download_file_from_url(input_data, file_path)
        return os.path.basename(file_path)
    elif input_type == "base64":
        # Base64인 경우 디코딩하여 저장
        logger.info(f"🔢 Base64 입력 처리")
        os.makedirs(comfyui_input_dir, exist_ok=True)
        file_path = os.path.abspath(os.path.join(comfyui_input_dir, f"{temp_dir}_{output_filename}"))
        save_base64_to_file(input_data, file_path)
        return os.path.basename(file_path)
    else:
        raise Exception(f"지원하지 않는 입력 타입: {input_type}")

        
def download_file_from_url(url, output_path):
    """URL에서 파일을 다운로드하는 함수"""
    try:
        # wget을 사용하여 파일 다운로드
        result = subprocess.run([
            'wget', '-O', output_path, '--no-verbose', url
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"✅ URL에서 파일을 성공적으로 다운로드했습니다: {url} -> {output_path}")
            return output_path
        else:
            logger.error(f"❌ wget 다운로드 실패: {result.stderr}")
            raise Exception(f"URL 다운로드 실패: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("❌ 다운로드 시간 초과")
        raise Exception("다운로드 시간 초과")
    except Exception as e:
        logger.error(f"❌ 다운로드 중 오류 발생: {e}")
        raise Exception(f"다운로드 중 오류 발생: {e}")


def save_base64_to_file(base64_data, output_path):
    """Base64 데이터를 파일로 저장하는 함수"""
    try:
        # Base64 문자열 디코딩
        decoded_data = base64.b64decode(base64_data)
        # 파일로 저장
        with open(output_path, 'wb') as f:
            f.write(decoded_data)

        logger.info(f"✅ Base64 입력을 '{output_path}' 파일로 저장했습니다.")
        return output_path
    except (binascii.Error, ValueError) as e:
        logger.error(f"❌ Base64 디코딩 실패: {e}")
        raise Exception(f"Base64 디코딩 실패: {e}")

def stage_image_to_comfyui_input(input_path, temp_dir, output_filename):
    """이미지 파일을 ComfyUI input 디렉토리에 복사하고 파일명을 반환"""
    if not input_path:
        raise Exception("이미지 경로가 비어 있습니다.")

    abs_input_path = os.path.abspath(input_path)
    if not os.path.isfile(abs_input_path):
        raise Exception(f"Invalid image file: {abs_input_path}")

    os.makedirs(comfyui_input_dir, exist_ok=True)
    target_name = f"{temp_dir}_{output_filename}"
    target_path = os.path.abspath(os.path.join(comfyui_input_dir, target_name))

    if abs_input_path != target_path:
        shutil.copy2(abs_input_path, target_path)
        logger.info(f"✅ 이미지 파일을 ComfyUI input으로 복사했습니다: {abs_input_path} -> {target_path}")
    else:
        logger.info(f"✅ 이미지 파일이 이미 ComfyUI input에 있습니다: {target_path}")

    return target_name
    
def queue_prompt(prompt):
    url = f"http://{server_address}:8188/prompt"
    logger.info(f"Queueing prompt to: {url}")
    p = {"prompt": prompt, "client_id": client_id}
    
    # Validate prompt structure before sending
    try:
        data = json.dumps(p).encode('utf-8')
    except Exception as json_error:
        logger.error(f"Failed to serialize prompt to JSON: {json_error}")
        logger.error(f"Prompt structure: {prompt}")
        raise Exception(f"Invalid prompt structure: {json_error}")
    
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        response = urllib.request.urlopen(req)
        return json.loads(response.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        logger.error(f"❌ HTTP Error {e.code}: {e.reason}")
        logger.error(f"❌ Server response: {error_body}")
        logger.error(f"❌ Request URL: {url}")
        logger.error(f"❌ Client ID: {client_id}")
        # Log a sample of the prompt (first few nodes) to avoid excessive logging
        try:
            prompt_keys = list(prompt.keys())[:5] if isinstance(prompt, dict) else "Not a dict"
            logger.error(f"❌ Prompt node IDs (first 5): {prompt_keys}")
            # Check for common issues
            for node_id, node_data in list(prompt.items())[:3]:
                if not isinstance(node_data, dict):
                    logger.error(f"❌ Node {node_id} is not a dict: {type(node_data)}")
                elif "inputs" not in node_data:
                    logger.error(f"❌ Node {node_id} missing 'inputs' key")
                elif "class_type" not in node_data:
                    logger.error(f"❌ Node {node_id} missing 'class_type' key")
        except Exception as log_error:
            logger.error(f"❌ Error while logging prompt details: {log_error}")
        raise Exception(f"ComfyUI API Error {e.code}: {error_body}")

def get_image(filename, subfolder, folder_type):
    url = f"http://{server_address}:8188/view"
    logger.info(f"Getting image from: {url}")
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"{url}?{url_values}") as response:
        return response.read()

def get_history(prompt_id):
    url = f"http://{server_address}:8188/history/{prompt_id}"
    logger.info(f"Getting history from: {url}")
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())

def get_videos(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_videos = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break
        else:
            continue

    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        videos_output = []
        if 'gifs' in node_output:
            for video in node_output['gifs']:
                # fullpath를 이용하여 직접 파일을 읽고 base64로 인코딩
                with open(video['fullpath'], 'rb') as f:
                    video_data = base64.b64encode(f.read()).decode('utf-8')
                videos_output.append(video_data)
        output_videos[node_id] = videos_output

    return output_videos

def load_workflow(workflow_path):
    with open(workflow_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def set_node_input(prompt, node_id, input_key, value, node_description=""):
    """Safely set a node input value with validation"""
    if node_id not in prompt:
        raise Exception(f"Node {node_id} ({node_description}) not found in workflow. Available nodes: {list(prompt.keys())[:20]}")
    if "inputs" not in prompt[node_id]:
        raise Exception(f"Node {node_id} ({node_description}) has no 'inputs' field")
    prompt[node_id]["inputs"][input_key] = value
    logger.debug(f"Set node {node_id} ({node_description}) input '{input_key}' = {value}")

def handler(job):
    job_input = job.get("input", {})

    logger.info(f"Received job input: {job_input}")
    task_id = f"task_{uuid.uuid4()}"

    # 이미지 입력 처리 (image_path, image_url, image_base64 중 하나만 사용)
    image_path = None
    if "image_path" in job_input:
        image_path = process_input(job_input["image_path"], task_id, "input_image.jpg", "path")
    elif "image_url" in job_input:
        image_path = process_input(job_input["image_url"], task_id, "input_image.jpg", "url")
    elif "image_base64" in job_input:
        image_path = process_input(job_input["image_base64"], task_id, "input_image.jpg", "base64")
    else:
        # 기본값 사용
        default_image_path = os.path.join(comfyui_input_dir, "example_image.png")
        if not os.path.isfile(default_image_path):
            raise Exception(f"기본 이미지 파일을 찾을 수 없습니다: {default_image_path}. image_path/image_url/image_base64 중 하나를 제공하세요.")
        image_path = os.path.basename(default_image_path)
        logger.info(f"기본 이미지 파일을 사용합니다: {default_image_path}")

    # 엔드 이미지 입력 처리 (end_image_path, end_image_url, end_image_base64 중 하나만 사용)
    end_image_path_local = None
    if "end_image_path" in job_input:
        end_image_path_local = process_input(job_input["end_image_path"], task_id, "end_image.jpg", "path")
    elif "end_image_url" in job_input:
        end_image_path_local = process_input(job_input["end_image_url"], task_id, "end_image.jpg", "url")
    elif "end_image_base64" in job_input:
        end_image_path_local = process_input(job_input["end_image_base64"], task_id, "end_image.jpg", "base64")
    
    # LoRA 설정 확인 - 배열로 받아서 처리
    lora_pairs = job_input.get("lora_pairs", [])
    
    # 최대 4개 LoRA까지 지원
    lora_count = min(len(lora_pairs), 4)
    if lora_count > len(lora_pairs):
        logger.warning(f"LoRA 개수가 {len(lora_pairs)}개입니다. 최대 4개까지만 지원됩니다. 처음 4개만 사용합니다.")
        lora_pairs = lora_pairs[:4]
    
    # 워크플로우 파일 선택 (end_image_*가 있으면 FLF2V 워크플로 사용)
    workflow_file = "/new_Wan22_flf2v_api.json" if end_image_path_local else "/new_Wan22_api.json"
    logger.info(f"Using {'FLF2V' if end_image_path_local else 'single'} workflow with {lora_count} LoRA pairs")
    
    prompt = load_workflow(workflow_file)
    
    # Validate workflow structure
    if not isinstance(prompt, dict):
        raise Exception(f"Workflow file {workflow_file} did not load as a dictionary")
    logger.info(f"Loaded workflow with {len(prompt)} nodes")
    
    length = job_input.get("length", 81)
    steps = job_input.get("steps", 10)

    # Validate required nodes exist
    required_nodes = ["244", "541", "135", "220", "540", "235", "236", "498"]
    missing_nodes = [node for node in required_nodes if node not in prompt]
    if missing_nodes:
        raise Exception(f"Workflow missing required nodes: {missing_nodes}. Available nodes: {list(prompt.keys())[:10]}")

    prompt["244"]["inputs"]["image"] = image_path
    prompt["541"]["inputs"]["num_frames"] = length
    prompt["135"]["inputs"]["positive_prompt"] = job_input["prompt"]
    prompt["135"]["inputs"]["negative_prompt"] = job_input.get("negative_prompt", "bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards")
    prompt["220"]["inputs"]["seed"] = job_input["seed"]
    prompt["540"]["inputs"]["seed"] = job_input["seed"]
    prompt["540"]["inputs"]["cfg"] = job_input["cfg"]
    # 해상도(폭/높이) 16배수 보정
    original_width = job_input["width"]
    original_height = job_input["height"]
    adjusted_width = to_nearest_multiple_of_16(original_width)
    adjusted_height = to_nearest_multiple_of_16(original_height)
    if adjusted_width != original_width:
        logger.info(f"Width adjusted to nearest multiple of 16: {original_width} -> {adjusted_width}")
    if adjusted_height != original_height:
        logger.info(f"Height adjusted to nearest multiple of 16: {original_height} -> {adjusted_height}")
    prompt["235"]["inputs"]["value"] = adjusted_width
    prompt["236"]["inputs"]["value"] = adjusted_height
    prompt["498"]["inputs"]["context_overlap"] = job_input.get("context_overlap", 48)
    prompt["498"]["inputs"]["context_frames"] = length
    
    # step 설정 적용
    if "834" in prompt:
        prompt["834"]["inputs"]["steps"] = steps
        logger.info(f"Steps set to: {steps}")
        lowsteps = int(steps*0.6)
        prompt["829"]["inputs"]["step"] = lowsteps
        logger.info(f"LowSteps set to: {lowsteps}")

    # 엔드 이미지가 있는 경우 617번 노드에 경로 적용 (FLF2V 전용)
    if end_image_path_local:
        prompt["617"]["inputs"]["image"] = end_image_path_local
    
    # LoRA 설정 적용 - HIGH LoRA는 노드 279, LOW LoRA는 노드 553
    if lora_count > 0:
        # HIGH LoRA 노드 (279번)
        high_lora_node_id = "279"
        
        # LOW LoRA 노드 (553번)
        low_lora_node_id = "553"
        
        # 입력받은 LoRA pairs 적용 (lora_1부터 시작)
        for i, lora_pair in enumerate(lora_pairs):
            if i < 4:  # 최대 4개까지만
                lora_high = lora_pair.get("high")
                lora_low = lora_pair.get("low")
                lora_high_weight = lora_pair.get("high_weight", 1.0)
                lora_low_weight = lora_pair.get("low_weight", 1.0)
                
                # HIGH LoRA 설정 (노드 279번, lora_1부터 시작)
                if lora_high:
                    prompt[high_lora_node_id]["inputs"][f"lora_{i+1}"] = lora_high
                    prompt[high_lora_node_id]["inputs"][f"strength_{i+1}"] = lora_high_weight
                    logger.info(f"LoRA {i+1} HIGH applied to node 279: {lora_high} with weight {lora_high_weight}")
                
                # LOW LoRA 설정 (노드 553번, lora_1부터 시작)
                if lora_low:
                    prompt[low_lora_node_id]["inputs"][f"lora_{i+1}"] = lora_low
                    prompt[low_lora_node_id]["inputs"][f"strength_{i+1}"] = lora_low_weight
                    logger.info(f"LoRA {i+1} LOW applied to node 553: {lora_low} with weight {lora_low_weight}")

    ws_url = f"ws://{server_address}:8188/ws?clientId={client_id}"
    logger.info(f"Connecting to WebSocket: {ws_url}")
    
    # 먼저 HTTP 연결이 가능한지 확인
    http_url = f"http://{server_address}:8188/"
    logger.info(f"Checking HTTP connection to: {http_url}")
    
    # HTTP 연결 확인 (최대 1분)
    max_http_attempts = 180
    for http_attempt in range(max_http_attempts):
        try:
            import urllib.request
            response = urllib.request.urlopen(http_url, timeout=5)
            logger.info(f"HTTP 연결 성공 (시도 {http_attempt+1})")
            break
        except Exception as e:
            logger.warning(f"HTTP 연결 실패 (시도 {http_attempt+1}/{max_http_attempts}): {e}")
            if http_attempt == max_http_attempts - 1:
                raise Exception("ComfyUI 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
            time.sleep(1)
    
    ws = websocket.WebSocket()
    # 웹소켓 연결 시도 (최대 3분)
    max_attempts = int(180/5)  # 3분 (1초에 한 번씩 시도)
    for attempt in range(max_attempts):
        import time
        try:
            ws.connect(ws_url)
            logger.info(f"웹소켓 연결 성공 (시도 {attempt+1})")
            break
        except Exception as e:
            logger.warning(f"웹소켓 연결 실패 (시도 {attempt+1}/{max_attempts}): {e}")
            if attempt == max_attempts - 1:
                raise Exception("웹소켓 연결 시간 초과 (3분)")
            time.sleep(5)
    
    # Final validation before sending prompt
    logger.info(f"🔍 Validating prompt structure before queue...")
    try:
        # Quick validation that prompt is serializable
        test_json = json.dumps({"prompt": prompt, "client_id": client_id})
        logger.info(f"✅ Prompt structure is valid JSON ({len(test_json)} bytes)")
        
        # Check for common issues in nodes
        nodes_validated = 0
        for node_id, node_data in prompt.items():
            if not isinstance(node_data, dict):
                raise Exception(f"Node {node_id} is not a dictionary: {type(node_data)}")
            if "class_type" not in node_data:
                raise Exception(f"Node {node_id} missing 'class_type'")
            if "inputs" not in node_data:
                raise Exception(f"Node {node_id} missing 'inputs'")
            nodes_validated += 1
        logger.info(f"✅ Validated {nodes_validated} nodes in workflow")

        # Ensure input images exist in ComfyUI input directory
        if image_path:
            image_full_path = os.path.join(comfyui_input_dir, image_path)
            if not os.path.isfile(image_full_path):
                raise Exception(f"Input image not found in ComfyUI input directory: {image_full_path}")
        if end_image_path_local:
            end_image_full_path = os.path.join(comfyui_input_dir, end_image_path_local)
            if not os.path.isfile(end_image_full_path):
                raise Exception(f"End image not found in ComfyUI input directory: {end_image_full_path}")
    except Exception as validation_error:
        logger.error(f"❌ Prompt validation failed: {validation_error}")
        raise
    
    videos = get_videos(ws, prompt)
    ws.close()

    # 이미지가 없는 경우 처리
    for node_id in videos:
        if videos[node_id]:
            return {"video": videos[node_id][0]}
    
    return {"error": "비디오를를 찾을 수 없습니다."}

runpod.serverless.start({"handler": handler})