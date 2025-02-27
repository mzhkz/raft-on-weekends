import os
import json
import subprocess
import time
import glob
import statistics

# 実験設定
STATE_TYPES = [
    "default",
    "o",
    "cca",
]


BASE_CONFIG = {
    "duration": 7,
    "client_nums": 3,
    "node_nums": 5,
    "write_ratio": 0.5,
    "requests_per_second": 130,
    "key_range": 50
}

def delete_dump_files():
    """dumpファイルとフォルダを削除する"""
    for file in glob.glob("dump/client_results/*", recursive=True):
        os.remove(file)
    for file in glob.glob("dump/experiment_results/*", recursive=True):
        os.remove(file)

def update_evaluation_config(config):
    """evaluation_config.jsonを更新する"""
    with open('evaluator_config.json', 'w') as f:
        json.dump(config, f, indent=2)

def build_docker_images():
    """Dockerイメージをビルドする"""
    subprocess.run(["docker-compose", "build"], check=True)

def run_docker_compose():
    """docker-compose upを実行する"""
    subprocess.run(["docker-compose", "up", "-d", "--build"], check=True)

def stop_and_remove_containers():
    """コンテナを停止して削除する"""
    subprocess.run(["docker-compose", "kill"], check=True)
    subprocess.run(["docker-compose", "rm", "-f", "-a"], check=True)

def collect_results(experiment_name, state_type, write_ratio):
    """実験結果を収集して集計する"""
    results = {
        "write_throughput": [],
        "write_latency": [],
        "write_success_rate": [],
        "write_requests": [],

        "read_throughput": [],
        "read_latency": [],
        "read_success_rate": [],
        "read_requests": []
    }

    
    # dumpディレクトリから結果ファイルを検索（client.pyの命名規則に合わせる）
    # 例: PerformanceEvaluator-client1-s10-r1_0-k100-d4.json
    files = glob.glob(f"dump/client_results/*{state_type}*-*.json")
    
    for file_path in files:
        with open(file_path, 'r') as f:
            # データを読み込む
            data = json.load(f)
            # 各タイムスタンプのデータを処理
            for i, entry in enumerate(data):
                if 'write' in entry:
                    if len(results['write_throughput']) <= i:
                        results['write_throughput'].append([])
                    results['write_throughput'][i].append(entry['write']['throughput'])
                    results['write_latency'].append(entry['write']['avg_latency'])
                    results['write_success_rate'].append(entry['write']['success_rate'])
                    results['write_requests'].append(entry['write']['requests'])
                if 'read' in entry:
                    if len(results['read_throughput']) <= i:
                        results['read_throughput'].append([])
                    results['read_throughput'][i].append(entry['read']['throughput'])
                    results['read_latency'].append(entry['read']['avg_latency'])
                    results['read_success_rate'].append(entry['read']['success_rate'])
                    results['read_requests'].append(entry['read']['requests'])
            
    # 平均と中央値を計算
    aggregated_results = {}
    for metric in results.keys():
        if results[metric]:
            if metric.endswith('latency') or metric.endswith('success_rate'):
                aggregated_results[f"{metric}_mean"] = statistics.mean(results[metric])
                aggregated_results[f"{metric}_median"] = statistics.median(results[metric])
                aggregated_results[f"{metric}_min"] = min(results[metric])
                aggregated_results[f"{metric}_max"] = max(results[metric])
            elif metric.endswith('throughput'):
                aggregated_results[f"{metric}_mean"] = statistics.mean([sum(results[metric][i]) for i in range(len(results[metric]))])
                aggregated_results[f"{metric}_median"] = statistics.median([sum(results[metric][i]) for i in range(len(results[metric]))])
                aggregated_results[f"{metric}_min"] = min([sum(results[metric][i]) for i in range(len(results[metric]))])
                aggregated_results[f"{metric}_max"] = max([sum(results[metric][i]) for i in range(len(results[metric]))])
            else:
                aggregated_results[f"{metric}_sum"] = sum(results[metric])
                aggregated_results[f"{metric}_min"] = min(results[metric])
                aggregated_results[f"{metric}_max"] = max(results[metric])

    if write_ratio == 0.0:
        if aggregated_results['read_throughput_mean'] <= 20 or aggregated_results['read_latency_mean'] < 0.2:
            return None
    elif write_ratio == 1.0:
        if aggregated_results['write_throughput_mean'] <= 20 or aggregated_results['write_latency_mean'] < 0.2:
            return None
    else:
        if aggregated_results['write_throughput_mean'] <= 5 or aggregated_results['write_latency_mean'] < 0.2 or aggregated_results['read_throughput_mean'] <= 3 or aggregated_results['read_latency_mean'] < 0.2:
            return None
    
    # 結果をJSONファイルに保存
    output_dir = "dump/experiment_results"
    os.makedirs(output_dir, exist_ok=True)
    
    with open(f"{output_dir}/{experiment_name}_{state_type}_results.json", 'w') as f:
        json.dump(aggregated_results, f, indent=2)

    # dumpファイルを削除
    for file in glob.glob(f"dump/client_results/*{state_type}*-*.json"):
        os.remove(file)
    
    return aggregated_results

def run_experiment(experiment_name, config, state_types):
    """実験を実行する"""
    results = {}
    
    for state_type in state_types:
        print("--------------------------------")
        print(f"実験 {experiment_name} を {state_type} で実行中...")

        
        # 既存の結果ファイルを削除
        for file in glob.glob("dump/*.json"):
            os.remove(file)
        
        # 設定を更新
        print(json.dumps(config, indent=2))
        node_nums = config["node_nums"]
        client_nums = config["client_nums"]
        update_evaluation_config(config)

        subprocess.run(["python", "generate-docker-compose.py", str(node_nums), str(client_nums), state_type])
        time.sleep(1)
        
        # Docker Composeを実行
        run_docker_compose()
        
        # プロセスが終了するのを待機
        print("プロセスが終了するのを待機しています...")
        while True:
            # 結果ファイルが生成されたかチェック（client.pyの命名規則に合わせる）
            result_files = glob.glob(f"dump/client_results/*{state_type}*-*.json")
            if len(result_files) >= client_nums:
                # print(f"結果ファイルが{client_nums}個生成されました。次に進みます。")
                break
            time.sleep(0.2)  # 2秒ごとにチェック
        
        # 結果を収集
        try:
            results[state_type] = collect_results(experiment_name, state_type, config["write_ratio"])
            print(f"実験 {experiment_name} の {state_type} の結果を収集しました。")
        except Exception as e:
            print(e)
            print("実験結果が不正です。再実行します。")
            run_experiment(experiment_name, config, [state_type])
        finally:
            # コンテナを停止して削除
            stop_and_remove_containers()
    
    return results

def experiment1():
    """実験1: キーのバリエーション、2^n (0 <= n <= 9, 1刻み), write_ratio = 0.5, クライアントの個数 3"""
    print("実験1を開始します...")
    
    base_config = BASE_CONFIG.copy()
    
    results = {}
    
    for n in range(0, 6):  # 0から6まで
        key_range = 2 ** n
        experiment_name = f"experiment1_keys_{key_range}"
        
        config = base_config.copy()
        config["key_range"] = key_range
        
        exp_results = run_experiment(experiment_name, config, STATE_TYPES)
        results[key_range] = exp_results
    
    # 全体の結果をJSONファイルに保存
    with open("dump/experiment_results/experiment1_all_results.json", 'r') as f:
        previous_results = json.load(f)
    for key in results.keys():
        previous_results[str(key)] = results[key]
        print(f"実験1の{key}の結果を保存します...")
    # 全体の結果をJSONファイルに保存
    with open("dump/experiment_results/experiment1_all_results.json", 'w') as f:
        json.dump(previous_results, f, indent=2)

def experiment2():
    """実験2: ノードの個数、n (4 <= n <= 9, 1刻み)、クライアントの個数 3, write_ratio = 1.0"""
    print("実験2を開始します...")
    
    base_config = BASE_CONFIG.copy()
    base_config["write_ratio"] = 1.0
    
    results = {}
    
    for n in range(4, 10):  # 4から9まで
        experiment_name = f"experiment2_nodes_{n}"
        
        config = base_config.copy()
        config["node_nums"] = n
        
        exp_results = run_experiment(experiment_name, config, STATE_TYPES)
        results[n] = exp_results
    
    # 全体の結果をJSONファイルに保存
    with open("dump/experiment_results/experiment2_all_results.json", 'r') as f:
        previous_results = json.load(f)
    for key in results.keys():
        previous_results[str(key)] = results[key]
        print(f"実験2の{key}の結果を保存します...")
    # 全体の結果をJSONファイルに保存
    with open("dump/experiment_results/experiment2_all_results.json", 'w') as f:
        json.dump(previous_results, f, indent=2)

def experiment3():
    """実験3: クライアントの個数 2^n (0 <= n <= 5, 1刻み), write_ratio = 1.0"""
    print("実験3を開始します...")
    
    base_config = BASE_CONFIG.copy()
    base_config["write_ratio"] = 1.0
    
    results = {}
    
    for n in range(4, 6):  # 0から5まで
        client_nums = 2 ** n
        experiment_name = f"experiment3_clients_{client_nums}"
        
        config = base_config.copy()
        config["client_nums"] = client_nums
        
        exp_results = run_experiment(experiment_name, config, STATE_TYPES)
        results[client_nums] = exp_results
    
    with open("dump/experiment_results/experiment3_all_results.json", 'r') as f:
        previous_results = json.load(f)
    for key in results.keys():
        previous_results[str(key)] = results[key]
        print(f"実験3の{key}の結果を保存します...")
    # 全体の結果をJSONファイルに保存
    with open("dump/experiment_results/experiment3_all_results.json", 'w') as f:
        json.dump(previous_results, f, indent=2)

def experiment4():
    """実験4: クライアントの個数 2^n (0 <= n <= 5, 1刻み), write_ratio = 0"""
    print("実験4を開始します...")
    
    base_config = BASE_CONFIG.copy()
    base_config["write_ratio"] = 0
    
    results = {}
    
    for n in range(0, 6):  # 0から5まで
        client_nums = 2 ** n
        experiment_name = f"experiment4_clients_{client_nums}"
        
        config = base_config.copy()
        config["client_nums"] = client_nums

        exp_results = run_experiment(experiment_name, config, STATE_TYPES)
        results[client_nums] = exp_results
    
    # 全体の結果をJSONファイルに保存
    with open("dump/experiment_results/experiment4_all_results.json", 'r') as f:
        previous_results = json.load(f)
    for key in results.keys():
        previous_results[str(key)] = results[key]
        print(f"実験4の{key}の結果を保存します...")
    # 全体の結果をJSONファイルに保存
    with open("dump/experiment_results/experiment4_all_results.json", 'w') as f:
        json.dump(previous_results, f, indent=2)

def main():
    # 実験結果保存ディレクトリを作成
    os.makedirs("dump/experiment_results", exist_ok=True)
    # delete_dump_files()
    
    # Dockerイメージをビルド
    # build_docker_images()
    
    # 各実験を実行
    # experiment1()
    # experiment2()
    experiment3()
    experiment4()
    
    print("すべての実験が完了しました。結果はdump/experiment_resultsディレクトリに保存されています。")

if __name__ == "__main__":
    main()





