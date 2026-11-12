"""A tiny study timer: work for a while, then take a short break."""
import time

WORK_MINUTES = 25
BREAK_MINUTES = 5


def countdown(minutes: int, label: str) -> None:
    print(f"{label}: {minutes} minutes")
    for left in range(minutes, 0, -1):
        print(f"  {left} min left")
        time.sleep(60)


if __name__ == "__main__":
    countdown(WORK_MINUTES, "Study")
    countdown(BREAK_MINUTES, "Break")
    print("Done. Mark the lesson as done in inPace!")
