import matplotlib.pyplot as plt
import numpy as np
import glob
import json
import os
def render_graph(x, throughput, latency, x_label, experiment_name, x_is_log):
    """グラフを描画する"""
    # データの準備
    # フォントサイズの設定
    plt.rcParams['font.size'] = 58  # デフォルトのフォントサイズを4倍に
    plt.rcParams['axes.labelsize'] = 58  # 軸ラベルのフォントサイズを4倍に
    plt.rcParams['axes.titlesize'] = 58  # タイトルのフォントサイズを4倍に
    plt.rcParams['legend.fontsize'] = 50  # 凡例のフォントサイズを4倍に
    plt.rcParams['xtick.labelsize'] = 58  # x軸目盛りのフォントサイズを4倍に
    plt.rcParams['ytick.labelsize'] = 53  # y軸目盛りのフォントサイズを4倍に
    plt.rcParams['font.family'] = 'Times New Roman' #全体のフォントを設定
    plt.rcParams['axes.grid'] = True # make grid
    plt.rcParams["legend.fancybox"] = False # 丸角
    plt.rcParams["legend.framealpha"] = 1 # 透明度の指定、0で塗りつぶしなし
    plt.rcParams["legend.edgecolor"] = 'black' # edgeの色を変更
    plt.rcParams["legend.handlelength"] = 1 # 凡例の線の長さを調節
    plt.rcParams["legend.handlelength"] = 2 # 凡例の線の長さを調節

    # グラフの作成 - 上部にレジェンド用の余白を確保
    fig, axes = plt.subplots(1, 2, figsize=(27, 14))
    
    # 上部に余白を追加
    # plt.subplots_adjust(top=1)

    throughput["TEERaft (Simulated)"] = [throughput["Raft"][i] * 0.89 for i in range(len(throughput["Raft"]))] # 89%に減少
    latency["TEERaft (Simulated)"] = [latency["Raft"][i] * 1.11 for i in range(len(latency["Raft"]))] # 11%増加

    # Throughputプロット
    max_throughput = max(max(throughput[label]) for label in throughput)
    lines = []
    for label in throughput:
        linestyle = '-'
        if label == "TEERaft (Simulated)":
            linestyle = '--'
        line, = axes[0].plot(x,
                    throughput[label],
                    label=label,
                    marker='o',
                    linestyle=linestyle,
                    markersize=20,  # マーカーサイズも大きく
                    linewidth=4)    # 線の太さも太く
        lines.append(line)
    # if x_is_log:
        # axes[0].set_xscale('log', base=2)
    axes[0].set_xlabel(x_label)
    axes[0].set_ylabel("Throughput (req/sec)")
    axes[0].set_ylim(bottom=0, top=max_throughput * 1.1)  # y軸を0から開始するように設定
    
    # タイトルを下に配置
    axes[0].set_title("(a) Throughput", pad=20, loc='center', y=-0.33)   

    # Latencyプロット
    max_latency = max(max(latency[label]) for label in latency)
    for label in latency:
        linestyle = '-'
        if label == "TEERaft (Simulated)":
            linestyle = '--'
        axes[1].plot(x,
                    latency[label],
                    label=label,
                    marker='o',
                    linestyle=linestyle,
                    markersize=20,  # マーカーサイズも大きく
                    linewidth=4)    # 線の太さも太く
    # axes[1].set_xscale('log', base=2)
    # axes[1].set_yscale('log')
    axes[1].set_xlabel(x_label)
    axes[1].set_ylabel("Latency (msec)")
    axes[1].set_ylim(bottom=0, top=max(max_latency * 1.1, 10))  # y軸を0から開始するように設定
    
    # タイトルを下に配置
    axes[1].set_title("(b) Latency", pad=20, loc='center', y=-0.33)
    
    # 両方のグラフで共通のレジェンドを図の上部に配置
    fig.legend(lines, [line.get_label() for line in lines], 
               loc='upper center', 
               bbox_to_anchor=(0.5, 1.0), 
               ncol=len(throughput))

    # レイアウト調整とPDFで保存
    plt.tight_layout(rect=[0, 0, 1, 0.9])  # 上部にレジェンド用の余白を確保
    os.makedirs('./dump/figures', exist_ok=True)
    plt.savefig(f'./dump/figures/{experiment_name}.pdf', bbox_inches='tight')
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
