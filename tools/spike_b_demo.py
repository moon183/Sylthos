"""Spike B（PLAN 步骤 5）：PyInstaller 打包验证用的最小 demo。

能打开摄像头并显示 MediaPipe 关键点即视为打包链路打通。
打包命令（在步骤 5 执行）：
    pyinstaller --onedir --noconsole --additional-hooks-dir=hooks --name spike_b tools/spike_b_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import mediapipe as mp


def main() -> None:
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("无法打开摄像头")
        sys.exit(1)
    hands = mp.solutions.hands.Hands(max_num_hands=1, model_complexity=0)
    print("Spike B 最小 demo 运行中，按 ESC 退出。")
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        frame = cv2.flip(frame, 1)
        result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if result.multi_hand_landmarks:
            for lm in result.multi_hand_landmarks:
                mp.solutions.drawing_utils.draw_landmarks(
                    frame, lm, mp.solutions.hands.HAND_CONNECTIONS)
        cv2.imshow("Spike B", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
    hands.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
