import matplotlib.pyplot as plt
import numpy as np
import glob
import json
import os
def render_graph(x, throughput, latency, x_label, experiment_name, x_is_log):
    """グラフを描画する"""
    # データの準備
    # フォントサイズの設定
    plt.rcParams['font.size'] = 40  # デフォルトのフォントサイズを4倍に
    plt.rcParams['axes.labelsize'] = 40  # 軸ラベルのフォントサイズを4倍に
    plt.rcParams['axes.titlesize'] = 40  # タイトルのフォントサイズを4倍に
    plt.rcParams['legend.fontsize'] = 40  # 凡例のフォントサイズを4倍に
    plt.rcParams['xtick.labelsize'] = 40  # x軸目盛りのフォントサイズを4倍に
    plt.rcParams['ytick.labelsize'] = 40  # y軸目盛りのフォントサイズを4倍に

    # グラフの作成
    fig, axes = plt.subplots(1, 2, figsize=(24, 12))  # フィギュアサイズも2倍に

    # Throughputプロット
    max_throughput = max(max(throughput[label]) for label in throughput)
    for label in throughput:
        axes[0].plot(x,
                    throughput[label],
                    label=label,
                    marker='o',
                    markersize=20,  # マーカーサイズも大きく
                    linewidth=4)    # 線の太さも太く
    # if x_is_log:
        # axes[0].set_xscale('log', base=2)
    axes[0].set_xlabel(x_label)
    axes[0].set_ylabel("Throughput (req/sec)")
    axes[0].set_title("(a) Throughput")
    axes[0].set_ylim(bottom=0, top=max_throughput + max_throughput * 0.2)  # y軸を0から開始するように設定
    axes[0].legend()

    # Latencyプロット
    max_latency = max(max(latency[label]) for label in latency)
    for label in latency:
        axes[1].plot(x,
                    latency[label],
                    label=label,
                    marker='o',
                    markersize=20,  # マーカーサイズも大きく
                    linewidth=4)    # 線の太さも太く
    # axes[1].set_xscale('log', base=2)
    # axes[1].set_yscale('log')
    axes[1].set_xlabel(x_label)
    axes[1].set_ylabel("Latency (msec)")
    axes[1].set_title("(b) Latency")
    axes[1].set_ylim(bottom=0, top=max(max_latency + max_latency, 15))  # y軸を0から開始するように設定
    axes[1].legend()

    # レイアウト調整とPDFで保存
    plt.tight_layout()
    os.makedirs('./dump/figures', exist_ok=True)
    plt.savefig(f'./dump/figures/{experiment_name}.pdf')
    plt.close()


def load_data(experiment_name):
    # states = {"default": "Raft", "o": "ORaft", "cca": "cca-Raft", "opt_cca": "opt-cca-Raft"}
    states = {"default": "Raft", "o": "ORaft", "cca": "cca-Raft"}
    file = glob.glob(f"dump/experiment_results/{experiment_name}_all_results.json")[0]
    with open(file, 'r') as f:
        data = json.load(f)
        x = data.keys()
        x_is_log = False
        write_throughput = {}
        write_latency = {}
        read_throughput = {}
        read_latency = {}

        for state, name in states.items():
            write_throughput[name] = [data[key][state]["write_throughput_max"] for key in x]
            write_latency[name] = [data[key][state]["write_latency_mean"] for key in x]
            read_throughput[name] = [data[key][state]["read_throughput_max"] for key in x]
            read_latency[name] = [data[key][state]["read_latency_mean"] for key in x]
        return x, write_throughput, write_latency, read_throughput, read_latency

def main():
    for experiment_name in ["experiment1", "experiment2", "experiment3", "experiment4"]:
        try:
            x, write_throughput, write_latency, read_throughput, read_latency = load_data(experiment_name)
            x_label = "Number of Clients"
            y_throughput = []
            y_latency = []
            if experiment_name == "experiment1": # キーのバリエーション
                x_label = "Number of Keys"
                x_is_log = True
                y_throughput = read_throughput
                y_latency = read_latency
            elif experiment_name == "experiment2": # ノードの数
                x_label = "Number of Nodes"
                y_throughput = write_throughput
                y_latency = write_latency
            elif experiment_name == "experiment3": # クライアントの数でwrite_ratio=1.0 (write)
                x_label = "Number of Clients"
                x_is_log = True
                y_throughput = write_throughput
                y_latency = write_latency
            elif experiment_name == "experiment4": # クライアントの数でwrite_ratio=0.0 (read)
                x_label = "Number of Clients"
                x_is_log = True
                y_throughput = read_throughput
                y_latency = read_latency
            # グラフを描画
            render_graph(x, y_throughput, y_latency, x_label, experiment_name, x_is_log) 
        except Exception as e:
            print(e)
            print(f"{experiment_name}をスキップします。")
            continue
if __name__ == "__main__":
    main()
