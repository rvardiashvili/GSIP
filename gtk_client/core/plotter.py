import matplotlib.pyplot as plt

def create_memory_figure(benchmark_data_list):
    """
    Returns a Matplotlib Figure for Peak Memory.
    """
    fig = plt.Figure(figsize=(10, 6), dpi=100)
    ax = fig.add_subplot(111)
    
    names = []
    mems = []
    colors = []
    
    for b in benchmark_data_list:
        model_conf = b.get('model_config', {})
        sys_stats = b.get('system_stats', {})
        
        name = model_conf.get('adapter_class', 'Unknown')
        label = b.get('meta', {}).get('start', 'Unknown')
        
        if 'process_ram_used_gb' in sys_stats:
            val = sys_stats['process_ram_used_gb'].get('max', 0)
            col = 'tab:blue'
        elif 'ram_used_gb' in sys_stats:
            val = sys_stats['ram_used_gb'].get('max', 0)
            col = 'tab:orange'
        else:
            val = 0
            col = 'gray'
            
        names.append(f"{name}\n{label[-8:]}")
        mems.append(val)
        colors.append(col)
        
    ax.bar(names, mems, color=colors)
    ax.set_ylabel('Peak Memory (GB)')
    ax.set_title('Memory Footprint Comparison')
    ax.tick_params(axis='x', rotation=45)
    
    # Native Style
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    
    fig.tight_layout()
    return fig

def create_time_figure(benchmark_data_list):
    """
    Returns a Matplotlib Figure for Duration.
    """
    fig = plt.Figure(figsize=(10, 6), dpi=100)
    ax = fig.add_subplot(111)
    
    names = []
    times = []
    
    for b in benchmark_data_list:
        meta = b.get('meta', {})
        model_conf = b.get('model_config', {})
        
        name = model_conf.get('adapter_class', 'Unknown')
        label = meta.get('start', 'Unknown')[-8:]
        val = meta.get('duration_seconds', 0)
        
        names.append(f"{name}\n{label}")
        times.append(val)
        
    ax.bar(names, times, color='tab:green')
    ax.set_ylabel('Execution Time (s)')
    ax.set_title('Performance Comparison')
    ax.tick_params(axis='x', rotation=45)
    
    # Native Style
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    
    fig.tight_layout()
    return fig

def create_time_series_figure(time_series_data, metric_key, title, ylabel):
    """
    Returns a Matplotlib Figure for Time Series.
    """
    fig = plt.Figure(figsize=(12, 6), dpi=100)
    ax = fig.add_subplot(111)
    
    timestamps = [x['timestamp'] for x in time_series_data]
    if not timestamps:
        return fig
        
    start_t = timestamps[0]
    t = [x - start_t for x in timestamps]
    values = [x.get(metric_key, 0) for x in time_series_data]
    
    ax.plot(t, values, marker='o', markersize=3, linewidth=2, color='#0078D4')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    
    # Native Style
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.5)
    
    fig.tight_layout()
    return fig
