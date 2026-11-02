# 源码结构索引

2026-10-23根据当前源码生成。定义名用于定位，不表示所有方法都是稳定公共API。核心契约见[HANDOVER](../HANDOVER.md)。

| 文件 | 顶层类/函数 |
|---|---|
| [src/__init__.py](../src/__init__.py) |  |
| [src/accept.py](../src/accept.py) | `AcceptRunner`, `run_acceptance` |
| [src/assistant_api.py](../src/assistant_api.py) | `AssistantError`, `AssistantCancelled`, `ApiSettings`, `ChatClient`, `NoRedirect`, `load_api_settings`, `save_api_settings` |
| [src/assistant_service.py](../src/assistant_service.py) | `generate_plan`, `retime_plan`, `rehearsal_context`, `analyse_rehearsal`, `format_plan_md`, `format_review_md` |
| [src/asr/__init__.py](../src/asr/__init__.py) |  |
| [src/asr/base.py](../src/asr/base.py) | `ASREngine`, `create_engine` |
| [src/asr/capture.py](../src/asr/capture.py) | `MicSegmenter`, `MicCapture`, `encode_wav` |
| [src/asr/hotwords.py](../src/asr/hotwords.py) | `parse_hotword_file`, `parse_script_file`, `_hamming`, `HotwordCorrector` |
| [src/asr/manager.py](../src/asr/manager.py) | `_correct_zh_line`, `ASRManager` |
| [src/asr/offline.py](../src/asr/offline.py) | `OfflineEngine`, `download_model` |
| [src/asr/online.py](../src/asr/online.py) | `DashScopeEngine` |
| [src/asr/streaming.py](../src/asr/streaming.py) | `StreamingEngine` |
| [src/calibration.py](../src/calibration.py) | `_median`, `_percentile`, `HandScaleMeasurer`, `SwipeMeasurer`, `HoldMeasurer`, `compute_suggestions`, `apply_suggestions`, `restore_defaults` |
| [src/camera_devices.py](../src/camera_devices.py) | `CameraDevice`, `list_cameras`, `resolve_camera_index` |
| [src/capture.py](../src/capture.py) | `CameraCapture` |
| [src/cli.py](../src/cli.py) | `cmd_record`, `cmd_replay`, `cmd_run`, `cmd_accept`, `cmd_train`, `build_parser`, `main` |
| [src/config.py](../src/config.py) | `_project_root`, `resolve_user_dir`, `load_config`, `setup_logging` |
| [src/control/__init__.py](../src/control/__init__.py) |  |
| [src/control/keyboard.py](../src/control/keyboard.py) | `set_win_timer_resolution`, `foreground_is_powerpoint`, `CursorStreamer`, `KeyboardController` |
| [src/control/ppt_com.py](../src/control/ppt_com.py) | `PptComController`, `launch_and_start_show` |
| [src/decision.py](../src/decision.py) | `GestureType`, `GestureEvent`, `Mode`, `DecisionContext`, `CommandRegistry`, `DecisionEngine` |
| [src/gesture_validation.py](../src/gesture_validation.py) | `recognizer_version`, `summary_text`, `ValidationSession`, `save_report`, `load_latest_report` |
| [src/gestures/__init__.py](../src/gestures/__init__.py) |  |
| [src/gestures/activation.py](../src/gestures/activation.py) | `ActivationSwitch` |
| [src/gestures/dollar.py](../src/gestures/dollar.py) | `_traj`, `_centroid`, `normalize_dollar`, `_path_distance`, `_distance_at_angle`, `_golden_section_distance`, `DollarRecognizer` |
| [src/gestures/eight_hold.py](../src/gestures/eight_hold.py) | `EightHoldDetector` |
| [src/gestures/filters.py](../src/gestures/filters.py) | `_LowPassFilter`, `OneEuroFilter`, `OneEuroFilter2D`, `MajorityVote` |
| [src/gestures/hold.py](../src/gestures/hold.py) | `HoldTimer`, `pose_state` |
| [src/gestures/laser.py](../src/gestures/laser.py) | `LaserToggleDetector`, `PinchClickDetector`, `LaserPointer` |
| [src/gestures/mlp.py](../src/gestures/mlp.py) | `TrajectoryMLP` |
| [src/gestures/nav.py](../src/gestures/nav.py) | `NavToggleDetector` |
| [src/gestures/ok_exit.py](../src/gestures/ok_exit.py) | `OkExitDetector` |
| [src/gestures/spotlight.py](../src/gestures/spotlight.py) | `SpotlightToggleDetector` |
| [src/gestures/static_pose.py](../src/gestures/static_pose.py) | `Pose`, `_cos_sim`, `_dist`, `PoseClassifier` |
| [src/gestures/swipe.py](../src/gestures/swipe.py) | `_State`, `SwipeDetector` |
| [src/gestures/tap.py](../src/gestures/tap.py) | `IndexTapDetector` |
| [src/gestures/trajectory.py](../src/gestures/trajectory.py) | `resample`, `normalize`, `stroke_feature`, `random_walk_feature`, `train_from_directory`, `_load_csv`, `_StrokeSegmenter`, `TrajectoryRecorder`, `CustomGestureDetector` |
| [src/gestures/twohand.py](../src/gestures/twohand.py) | `TwoHandZoomDetector` |
| [src/gestures/zoom.py](../src/gestures/zoom.py) | `PoseEdgeDetector`, `PalmSlideTracker` |
| [src/gui/__init__.py](../src/gui/__init__.py) |  |
| [src/gui/asr_page.py](../src/gui/asr_page.py) | `LevelMeter`, `_NavigationWrap`, `_StableBodyLabel`, `_StableCaptionLabel`, `ASRPage` |
| [src/gui/assistant_panel.py](../src/gui/assistant_panel.py) | `ApiSettingsDialog`, `AssistantPanel` |
| [src/gui/camera_preview.py](../src/gui/camera_preview.py) | `CameraPreview` |
| [src/gui/camera_selector.py](../src/gui/camera_selector.py) | `CameraSelector` |
| [src/gui/custom_gesture_page.py](../src/gui/custom_gesture_page.py) | `TrajectoryPreview`, `CustomGesturePage` |
| [src/gui/floating_panel.py](../src/gui/floating_panel.py) | `FloatingPanel` |
| [src/gui/fluent_window.py](../src/gui/fluent_window.py) | `PreviewPage`, `PracticePage`, `_NoWheelSpinBox`, `SettingsPage`, `LogPage`, `FluentMainWindow` |
| [src/gui/help_page.py](../src/gui/help_page.py) | `GestureHelpPage`, `HelpDialog` |
| [src/gui/main_window.py](../src/gui/main_window.py) | `MainWindow` |
| [src/gui/overlays_mixin.py](../src/gui/overlays_mixin.py) | `OverlaysMixin` |
| [src/gui/practice_timeline.py](../src/gui/practice_timeline.py) | `PracticeTimeline` |
| [src/gui/presentation_page.py](../src/gui/presentation_page.py) | `PresentationPage` |
| [src/gui/rehearsal_page.py](../src/gui/rehearsal_page.py) | `_note`, `_RevealClip`, `ResultView`, `RehearsalPage` |
| [src/gui/selftest_page.py](../src/gui/selftest_page.py) | `GestureTestDialog` |
| [src/gui/status_overlay.py](../src/gui/status_overlay.py) | `ClickableLabel`, `ThumbLabel`, `StatusOverlay` |
| [src/gui/theme_page.py](../src/gui/theme_page.py) | `theme_palette`, `accent_color`, `apply_pure_black`, `apply_theme_settings`, `ColorTile`, `ColorTileGrid`, `GradientSlider`, `_ToneCell`, `ToneGrid`, `PaletteDialog`, `_ModeCard`, `ThemePage` |
| [src/gui/theme_style.py](../src/gui/theme_style.py) | `luminance`, `contrast`, `_scheme`, `color_scheme`, `current_scheme`, `CardWidget`, `_NavigationTint`, `window_background`, `ThemeStyleController` |
| [src/gui/title_bar.py](../src/gui/title_bar.py) | `_FullHeightPaintFilter`, `_paint_full_height`, `_restyle_title_label`, `apply_title_bar_tweaks` |
| [src/gui/toast.py](../src/gui/toast.py) | `Toast` |
| [src/gui/validation_panel.py](../src/gui/validation_panel.py) | `ValidationPanel` |
| [src/gui/wizard_inline.py](../src/gui/wizard_inline.py) | `_sub_card`, `WizardPanel`, `InlineWizard` |
| [src/gui/worker.py](../src/gui/worker.py) | `GestureWorker`, `_draw_landmarks`, `_draw_hud` |
| [src/main.py](../src/main.py) | `main` |
| [src/overlay.py](../src/overlay.py) | `TransparentOverlay`, `FollowSmoother`, `ThumbnailGridOverlay`, `LaserOverlay`, `SpotlightOverlay`, `MagnifierOverlay`, `PointerRingOverlay`, `CountdownOverlay`, `NotesOverlay`, `wrapped_lines`, `SubtitleOverlay` |
| [src/pipeline.py](../src/pipeline.py) | `build_controls`, `Pipeline` |
| [src/plugins.py](../src/plugins.py) | `TextMessageBus` |
| [src/presentation_materials.py](../src/presentation_materials.py) | `MaterialImportError`, `read_pptx` |
| [src/presentation_store.py](../src/presentation_store.py) | `PresentationStore`, `context_label`, `validate_presentation_context` |
| [src/recorder.py](../src/recorder.py) | `hand_frame_to_dict`, `dict_to_hand_frame`, `RecordingWriter`, `load_recording` |
| [src/rehearsal.py](../src/rehearsal.py) | `_locked`, `RehearsalRecorder`, `command_label`, `report_time_text`, `format_report_md`, `_md`, `format_totals_md` |
| [src/rehearsal_store.py](../src/rehearsal_store.py) | `RehearsalStore` |
| [src/tracking.py](../src/tracking.py) | `HandFrame`, `compute_hand_scale`, `compute_crop_square`, `remap_to_frame`, `HandTracker` |
