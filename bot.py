"""
WeChat Jump Bot
Copyright (c) 2019 by SilentByte <https://silentbyte.com/>
"""

import math
import time
import cv2
import serial
import threading


class State:
    # Url from which to retrieve the live feed.
    stream_url = 'http://192.168.0.162:9999/video/mjpeg'

    # Serial port to which the Arduino is connected.
    serial_port = '/dev/ttyUSB0'

    # Represents the serial interface.
    arduino = None

    # Serial connection speed in baud.
    baud_rate = 9600

    # Time to wait between turns in milliseconds.
    turn_duration = 4000

    # Local render scale factor.
    display_scale = 0.75

    # Expected dimensions of the video feed.
    frame_width = 720
    frame_height = 1280

    # "Deadzone" around the frame that will be ignored.
    frame_margin = 90

    # Image of the player used for template matching.
    player_figure = None

    # Scale of the player template image (figure.png) in relation to the player size in the live feed.
    player_figure_scale = 0.75

    # Center offset in pixels from the bottom of the player figure.
    player_base_offset = 20

    # Offset from the top in pixels of where the player figure is expected to be.
    player_window_offset = 300

    # Height of the window in pixels in which the player is expected to be.
    player_window_height = 200

    # Player position (x, y) in pixels.
    player_position = (0, 0)

    # Area in which the player is located (top-left corner, bottom-right corner) in pixels.
    player_bounds = (0, 0, 0, 0)

    # Center of the platform (x, y) in pixels.
    platform_position = (0, 0)

    # Duration of the current jump in milliseconds.
    tap_duration = 0

    # Factor 'f' that determines the linear relationship between jump distance and duration.
    tap_multiplier = 2.45

    # Constant servo delay 'c' in milliseconds that is added to each jump duration.
    tap_delay = 85

    # Current frame.
    frame = None

    # When changed to false, the bot will be terminated.
    running = True


state = State()
state.arduino = serial.Serial(state.serial_port, state.baud_rate)
state.player_figure = cv2.resize(cv2.imread('figure.png'),
                                 None,
                                 fx=state.player_figure_scale,
                                 fy=state.player_figure_scale)


def millis():
    return time.time() * 1000


def send_command(command):
    if getattr(send_command, 'last', None) == command:
        return

    state.arduino.write(command)
    print(command)
    send_command.last = command


def process_events():
    if cv2.waitKey(1) & 0xff == 27:
        state.running = False


def read_frame_thread():
    try:
        capture = cv2.VideoCapture(state.stream_url)
        while state.running:
            _, frame = capture.read()
            state.frame = frame
            time.sleep(0.01)

    except Exception as e:
        print(e)
        state.running = False


def detect_player_position(frame):
    height, width, _ = frame.shape
    player_height, player_width, _ = state.player_figure.shape

    cropped = frame[state.player_window_offset:height - state.player_window_height, 0:width]
    player = cv2.matchTemplate(cropped, state.player_figure, cv2.TM_CCOEFF_NORMED)
    _min_val, _max_val, _min_loc, max_loc = cv2.minMaxLoc(player)

    state.player_position = (int(max_loc[0] + player_width / 2),
                             int(max_loc[1] + state.player_window_offset + player_height - state.player_base_offset))

    state.player_bounds = (int(max_loc[0]), int(max_loc[1] + state.player_window_offset),
                           int(max_loc[0] + player_width), int(max_loc[1] + state.player_window_offset + player_height))


def detect_platform_position(frame):
    frame = frame.copy()
    height, width, _ = frame.shape

    frame = cv2.medianBlur(frame, 7)
    frame = cv2.Canny(frame, 10, 50)

    cv2.imshow('shadow', cv2.resize(frame, None, fx=state.display_scale, fy=state.display_scale))

    # Remove margins.
    cv2.rectangle(frame, (0, 0), (width, state.frame_margin), (0, 0, 0), cv2.FILLED)
    cv2.rectangle(frame, (0, state.frame_margin), (state.frame_margin, height), (0, 0, 0), cv2.FILLED)
    cv2.rectangle(frame, (width - state.frame_margin, 0), (width, height), (0, 0, 0), cv2.FILLED)
    cv2.rectangle(frame, (0, height - state.frame_margin), (width, height), (0, 0, 0), cv2.FILLED)

    # Remove the top 1/3 of the screen (mainly to get rid of the score).
    cv2.rectangle(frame,
                  (0, 0),
                  (width, height // 3),
                  (0, 0, 0), cv2.FILLED)

    # Remove platform-overlapping player.
    cv2.rectangle(frame,
                  (state.player_bounds[0], state.player_bounds[1]),
                  (state.player_bounds[2], state.player_bounds[3]),
                  (0, 0, 0), cv2.FILLED)

    # Remove everything below the top 1/3 of the player's body.
    cv2.rectangle(frame,
                  (0, state.player_bounds[1] + (state.player_bounds[3] - state.player_bounds[1]) // 3),
                  (width, height),
                  (0, 0, 0), cv2.FILLED)

    top_offset = height // 6
    frame = frame[top_offset:state.player_position[1], 0:width]

    # Try to find the top-most platform's center.
    crop_height, crop_width = frame.shape
    platform_x = 0
    platform_y = 0
    max_x = 0

    for y in range(crop_height):
        for x in range(crop_width):
            if frame[y, x] == 255:
                if platform_x == 0:
                    platform_x = x
                if x > max_x:
                    platform_y = y
                    max_x = x

    state.platform_position = (platform_x, platform_y + top_offset)


def calculate_tap_duration():
    distance = math.sqrt((state.player_position[0] - state.platform_position[0]) ** 2
                         + (state.player_position[1] - state.platform_position[1]) ** 2)

    state.tap_duration = (distance * state.tap_multiplier + state.tap_delay)


def perform_jump_thread():
    while state.running:
        time.sleep(state.turn_duration / 1000)

        start_time = millis()
        while millis() < start_time + state.tap_duration:
            send_command(b'D')

        # Burst UP command.
        for _ in range(64):
            send_command(b'U')


threading.Thread(target=read_frame_thread).start()
threading.Thread(target=perform_jump_thread).start()

while state.running:
    if state.frame is None:
        time.sleep(0.01)
        continue

    frame = state.frame
    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    frame = cv2.resize(frame, dsize=(state.frame_width, state.frame_height))

    detect_player_position(frame)
    detect_platform_position(frame)
    calculate_tap_duration()

    # Render player position and bounds.
    frame = cv2.circle(frame, state.player_position, 7, (0, 0, 255), -1)
    frame = cv2.rectangle(frame, (state.player_bounds[0], state.player_bounds[1]),
                          (state.player_bounds[2], state.player_bounds[3]),
                          (0, 0, 255), 1)

    cv2.rectangle(frame,
                  (state.frame_margin, state.frame_margin),
                  (state.frame_width - state.frame_margin, state.frame_height - state.frame_margin),
                  (0, 0, 255))

    # Render platform position.
    frame = cv2.circle(frame, state.platform_position, 7, (0, 0, 255), -1)

    # Render jump predictions.
    frame = cv2.line(frame, state.player_position, state.platform_position, (0, 255, 0), 2)
    frame = cv2.putText(frame,
                        str(int(state.tap_duration)) + 'ms',
                        ((state.player_position[0] + state.platform_position[0]) // 2,
                         (state.player_position[1] + state.platform_position[1]) // 2),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 0, 255))

    cv2.imshow('frame', cv2.resize(frame, None, fx=state.display_scale, fy=state.display_scale))
    process_events()
