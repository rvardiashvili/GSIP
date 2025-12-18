import json
import statistics

def process_benchmark_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Split by the separator we inserted
    # Note: We need to handle potential newlines around the split tag
    reports_raw = content.split('---SPLIT---')
    results = []
    
    # Manual Mapping based on order we appended them
    model_names = ["Prithvi-100M", "ResNet-50 (All)", "ResNet-50 (S2)", "ConvNeXt-S2"]
    
    for i, report_str in enumerate(reports_raw):
        clean_str = report_str.strip()
        if not clean_str: continue
        if i >= len(model_names): break
        
        try:
            # Try to fix common JSON concat issues if any (though split should handle it)
            if clean_str.startswith(r'\n'): clean_str = clean_str[2:]
            
            data = json.loads(clean_str)
            
            # System Info
            sys_info = data['system']
            cpu = f"{sys_info['cpu_count_physical']} Cores ({sys_info['cpu_count_logical']} Logical)"
            ram_total = f"{sys_info['ram_total_gb']} GB"
            gpu = sys_info.get('gpu_name', 'Unknown')
            
            # Time Series Analysis
            ts = data['time_series']
            
            gpu_utils = [x.get('gpu_util_percent', 0) for x in ts]
            gpu_temps = [x.get('gpu_temp_c', 0) for x in ts]
            ram_used = [x.get('ram_used_gb', 0) for x in ts]
            gpu_mem = [x.get('gpu_mem_used_gb', 0) for x in ts]
            
            avg_gpu_util = statistics.mean(gpu_utils) if gpu_utils else 0
            max_gpu_temp = max(gpu_temps) if gpu_temps else 0
            max_ram = max(ram_used) if ram_used else 0
            max_vram = max(gpu_mem) if gpu_mem else 0
            duration = data['meta']['duration_seconds']
            
            results.append({
                "model": model_names[i],
                "duration": round(duration, 2),
                "avg_gpu_util": round(avg_gpu_util, 1),
                "max_gpu_temp": max_gpu_temp,
                "max_ram": max_ram,
                "max_vram": max_vram,
                "system": {"cpu": cpu, "ram": ram_total, "gpu": gpu}
            })
            
        except json.JSONDecodeError as e:
            # Fallback: Try to find start/end braces if there is garbage
            try:
                start = clean_str.find('{')
                end = clean_str.rfind('}') + 1
                if start != -1 and end != -1:
                    data = json.loads(clean_str[start:end])
                    # (Repeat extraction logic - refactor later)
                    sys_info = data['system']
                    cpu = f"{sys_info['cpu_count_physical']} Cores ({sys_info['cpu_count_logical']} Logical)"
                    ram_total = f"{sys_info['ram_total_gb']} GB"
                    gpu = sys_info.get('gpu_name', 'Unknown')
                    ts = data['time_series']
                    gpu_utils = [x.get('gpu_util_percent', 0) for x in ts]
                    gpu_temps = [x.get('gpu_temp_c', 0) for x in ts]
                    ram_used = [x.get('ram_used_gb', 0) for x in ts]
                    gpu_mem = [x.get('gpu_mem_used_gb', 0) for x in ts]
                    avg_gpu_util = statistics.mean(gpu_utils) if gpu_utils else 0
                    max_gpu_temp = max(gpu_temps) if gpu_temps else 0
                    max_ram = max(ram_used) if ram_used else 0
                    max_vram = max(gpu_mem) if gpu_mem else 0
                    duration = data['meta']['duration_seconds']
                    results.append({
                        "model": model_names[i],
                        "duration": round(duration, 2),
                        "avg_gpu_util": round(avg_gpu_util, 1),
                        "max_gpu_temp": max_gpu_temp,
                        "max_ram": max_ram,
                        "max_vram": max_vram,
                        "system": {"cpu": cpu, "ram": ram_total, "gpu": gpu}
                    })
            except:
                print(f"Error decoding JSON for report {i}: {e}")
                continue
            
    return results

if __name__ == "__main__":
    results = process_benchmark_file('temp_all_benchmarks.json')
    
    # Generate Markdown Table
    print(f"### 5.1.1 Validated Hardware Specifications")
    if results:
        sys = results[0]['system']
        print(f"*   **CPU:** {sys['cpu']}")
        print(f"*   **RAM:** {sys['ram']}")
        print(f"*   **GPU:** {sys['gpu']}")
    
    print("\n### 5.2.1 Quantitative Performance (Measured)")
    print("| Model | Duration (s) | GPU Util (Avg %) | Peak Temp (°C) | Peak VRAM (GB) | Peak RAM (GB) |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for r in results:
        print(f"| {r['model']} | {r['duration']} | {r['avg_gpu_util']}% | {r['max_gpu_temp']} | {r['max_vram']} | {r['max_ram']} |")