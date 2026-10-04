import asyncio
import sys
import os

INTERVAL = 7 * 24 * 60 * 60


async def run_script(script):
    path = os.path.join(os.path.dirname(__file__), script)
    print(f"Starting: {script}")

    proc = await asyncio.create_subprocess_exec(
        sys.executable, path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    out, err = await proc.communicate()

    if out:
        print(out.decode().strip())
    if err:
        print(err.decode().strip())

    if proc.returncode != 0:
        print(f"Error in {script}")
        return False

    print(f"Finished: {script}")
    return True


async def retrain_task(interval=INTERVAL):
    print(f"Retrainer started. Interval: {interval}s")

    scripts = ['data_fetcher.py', 'features_market.py', 'train_regime.py']

    while True:
        await asyncio.sleep(interval)
        print("\nScheduled retraining triggered...")

        success = True
        for script in scripts:
            if not await run_script(script):
                success = False
                break

        if success:
            print("Retraining completed.")