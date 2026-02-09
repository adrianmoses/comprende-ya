import asyncio
import websockets
import numpy as np
import json
from statistics import mean, stdev
import matplotlib.pyplot as plt


async def run_benchmark(num_tests=10):
    """Ejecuta múltiples tests y recopila estadísticas"""
    uri = "ws://localhost:8765/ws/voice"

    results = {
        "stt": [],
        "llm": [],
        "tts": [],
        "total": []
    }

    print(f"🧪 Ejecutando {num_tests} tests...")

    async with websockets.connect(uri) as websocket:
        for i in range(num_tests):
            # Audio de prueba
            audio_data = np.zeros(32000, dtype=np.int16)  # 2s @ 16kHz

            await websocket.send(audio_data.tobytes())

            # Recibir respuesta
            _ = await websocket.recv()  # audio
            metrics_json = await websocket.recv()  # metrics

            metrics = json.loads(metrics_json)["data"]

            results["stt"].append(metrics["stt_ms"])
            results["llm"].append(metrics["llm_ms"])
            results["tts"].append(metrics["tts_ms"])
            results["total"].append(metrics["total_ms"])

            print(f"  Test {i + 1}/{num_tests}: {metrics['total_ms']:.2f}ms")

    # Estadísticas
    print("\n📊 RESULTADOS:")
    print("=" * 50)
    for component in ["stt", "llm", "tts", "total"]:
        data = results[component]
        print(f"\n{component.upper()}:")
        print(f"  Media:      {mean(data):.2f}ms")
        print(f"  Std Dev:    {stdev(data):.2f}ms")
        print(f"  Min:        {min(data):.2f}ms")
        print(f"  Max:        {max(data):.2f}ms")

    # Visualización
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('Voice Agent Performance Benchmark', fontsize=16)

    components = ["stt", "llm", "tts", "total"]
    for idx, (ax, comp) in enumerate(zip(axes.flat, components)):
        ax.hist(results[comp], bins=20, edgecolor='black', alpha=0.7)
        ax.set_title(f'{comp.upper()} Latency')
        ax.set_xlabel('Latency (ms)')
        ax.set_ylabel('Frequency')
        ax.axvline(mean(results[comp]), color='r', linestyle='--',
                   label=f'Mean: {mean(results[comp]):.2f}ms')
        ax.legend()

    plt.tight_layout()
    plt.savefig('benchmark_results.png')
    print("\n📈 Gráfico guardado en benchmark_results.png")


if __name__ == "__main__":
    asyncio.run(run_benchmark(num_tests=20))