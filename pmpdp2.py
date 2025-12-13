#!/usr/bin/env python3



import sys, threading, time, os, st7789, subprocess

from gpiozero import Button

from PIL import Image, ImageDraw, ImageFont

from mpd import MPDClient

import json



# グローバル変数

directory = os.path.expanduser("~")

if directory == "/root":

    directory = "/home/pi"



# 画面状態

screen_off = False



# GPIO設定

button_action = Button(5)   # 決定

button_back = Button(6)      # 戻る

button_up = Button(16)       # 上/音量アップ

button_down = Button(20)     # 下/音量ダウン



# MPDクライアント

mpd_client = MPDClient()

mpd_client.timeout = 10

mpd_client.idletimeout = None



# UI状態管理

current_screen = "main_menu"  # main_menu, library, now_playing, queue

menu_stack = []  # メニュー階層管理

selected_index = 0

library_path = ""  # 現在のライブラリパス

library_items = []

queue_items = []

action_menu_visible = False

action_menu_items = []

action_menu_index = 0

last_button_time = 0

button_click_count = 0

moving_queue_item = False

moving_item_index = -1



# ディスプレイ設定

display_type = "square"



def get_wifi_status():

    """WiFiの状態を取得"""

    try:

        result = subprocess.run(['ip', 'link', 'show', 'wlan0'], 

                              capture_output=True, text=True, timeout=2)

        return 'UP' in result.stdout and 'state UP' in result.stdout

    except Exception as e:

        print(f"Error getting WiFi status: {e}")

        return False



def toggle_wifi():

    """WiFiのON/OFF切り替え"""

    try:

        if get_wifi_status():

            subprocess.run(['sudo', 'ip', 'link', 'set', 'wlan0', 'down'], timeout=5)

        else:

            subprocess.run(['sudo', 'ip', 'link', 'set', 'wlan0', 'up'], timeout=5)

    except Exception as e:

        print(f"Error toggling WiFi: {e}")



def set_backlight(state):

    """バックライトのON/OFF"""

    global screen_off

    try:

        if state:

            disp.set_backlight(1)

            screen_off = False

        else:

            disp.set_backlight(0)

            screen_off = True

    except Exception as e:

        print(f"Error setting backlight: {e}")



def shutdown_system():

    """システムをシャットダウン"""

    set_backlight(False)

    time.sleep(0.5)

    subprocess.run(['sudo', 'shutdown', '-h', 'now'])



def reboot_system():

    """システムを再起動"""

    set_backlight(False)

    time.sleep(0.5)

    subprocess.run(['sudo', 'reboot'])

    """MPDに接続"""

    try:

        mpd_client.connect("localhost", 6600)

        print("MPD connected successfully")

        return True

    except Exception as e:

        print(f"MPD connection error: {e}")

        return False



def get_library_items(path=""):

    """ライブラリアイテムを取得"""

    try:

        items = []

        result = mpd_client.lsinfo(path)

        

        for item in result:

            if 'directory' in item:

                items.append({

                    'type': 'directory',

                    'name': item['directory'].split('/')[-1],

                    'path': item['directory']

                })

            elif 'file' in item:

                title = item.get('title', item['file'].split('/')[-1])

                items.append({

                    'type': 'file',

                    'name': title,

                    'path': item['file'],

                    'artist': item.get('artist', ''),

                    'album': item.get('album', '')

                })

            elif 'playlist' in item:

                items.append({

                    'type': 'playlist',

                    'name': item['playlist'],

                    'path': item['playlist']

                })

        

        return items

    except Exception as e:

        print(f"Error getting library items: {e}")

        return []



def get_queue_items():

    """再生キューを取得"""

    try:

        items = []

        playlist = mpd_client.playlistinfo()

        

        for item in playlist:

            title = item.get('title', item['file'].split('/')[-1])

            items.append({

                'id': item['id'],

                'pos': item['pos'],

                'name': title,

                'artist': item.get('artist', ''),

                'album': item.get('album', '')

            })

        

        return items

    except Exception as e:

        print(f"Error getting queue: {e}")

        return []



def get_current_status():

    """現在の再生状態を取得"""

    try:

        status = mpd_client.status()

        current_song = mpd_client.currentsong()

        

        return {

            'state': status.get('state', 'stop'),

            'elapsed': float(status.get('elapsed', 0)),

            'duration': float(status.get('duration', 0)),

            'volume': int(status.get('volume', 50)),

            'repeat': status.get('repeat', '0') == '1',

            'random': status.get('random', '0') == '1',

            'title': current_song.get('title', ''),

            'artist': current_song.get('artist', ''),

            'album': current_song.get('album', ''),

            'file': current_song.get('file', '')

        }

    except Exception as e:

        print(f"Error getting status: {e}")

        return None



def play_now(path, is_playlist=False):

    """今すぐ再生"""

    try:

        mpd_client.clear()

        if is_playlist:

            mpd_client.load(path)

        else:

            mpd_client.add(path)

        mpd_client.play(0)

    except Exception as e:

        print(f"Error playing: {e}")



def add_to_queue(path, is_playlist=False):

    """キューの最後に追加"""

    try:

        if is_playlist:

            mpd_client.load(path)

        else:

            mpd_client.add(path)

    except Exception as e:

        print(f"Error adding to queue: {e}")



def add_next(path, is_playlist=False):

    """次に割込追加"""

    try:

        status = mpd_client.status()

        current_pos = int(status.get('song', -1))

        

        if is_playlist:

            mpd_client.load(path)

        else:

            mpd_client.add(path)

        

        # 最後に追加された曲を現在の次に移動

        playlist = mpd_client.playlistinfo()

        if playlist:

            last_pos = len(playlist) - 1

            mpd_client.move(last_pos, current_pos + 1)

    except Exception as e:

        print(f"Error adding next: {e}")



def show_action_menu(item):

    """アクションメニューを表示"""

    global action_menu_visible, action_menu_items, action_menu_index

    

    if current_screen == "library":

        action_menu_items = ["今すぐ再生", "キューの最後に追加", "次に割込追加"]

    elif current_screen == "queue":

        action_menu_items = ["移動", "削除", "今すぐ再生"]

    

    action_menu_visible = True

    action_menu_index = 0



def handle_action_menu_selection():

    """アクションメニューの選択を処理"""

    global action_menu_visible, moving_queue_item, moving_item_index

    

    action = action_menu_items[action_menu_index]

    

    if current_screen == "library":

        item = library_items[selected_index]

        is_playlist = item['type'] == 'playlist'

        

        if action == "今すぐ再生":

            play_now(item['path'], is_playlist)

        elif action == "キューの最後に追加":

            add_to_queue(item['path'], is_playlist)

        elif action == "次に割込追加":

            add_next(item['path'], is_playlist)

    

    elif current_screen == "queue":

        if selected_index < 2:  # シャッフル/リピート

            return

        

        item = queue_items[selected_index - 2]

        

        if action == "移動":

            moving_queue_item = True

            moving_item_index = selected_index

            action_menu_visible = False

            return

        elif action == "削除":

            try:

                mpd_client.deleteid(item['id'])

            except Exception as e:

                print(f"Error deleting: {e}")

        elif action == "今すぐ再生":

            try:

                mpd_client.play(int(item['pos']))

            except Exception as e:

                print(f"Error playing: {e}")

    

    action_menu_visible = False



def handle_button_action(bt):

    """アクションボタン処理"""

    global current_screen, selected_index, library_path, library_items

    global menu_stack, action_menu_visible, action_menu_index

    global last_button_time, button_click_count

    global moving_queue_item, moving_item_index, queue_items, screen_off

    

    # 消灯中の場合は点灯のみ

    if screen_off:

        set_backlight(True)

        update_display()

        return

    

    # ダブルクリック検出

    current_time = time.time()

    if current_time - last_button_time < 2.0:

        button_click_count += 1

    else:

        button_click_count = 1

    last_button_time = current_time

    

    # 再生中画面でのダブルクリック→スキップ

    if current_screen == "now_playing" and button_click_count == 2:

        try:

            mpd_client.next()

        except Exception as e:

            print(f"Error skipping: {e}")

        button_click_count = 0

        return

    

    # 再生中画面でのシングルクリック→再生/停止

    if current_screen == "now_playing" and button_click_count == 1:

        time.sleep(0.3)  # ダブルクリック待ち

        if button_click_count == 1:

            try:

                status = mpd_client.status()

                if status['state'] == 'play':

                    mpd_client.pause()

                else:

                    mpd_client.play()

            except Exception as e:

                print(f"Error toggling play: {e}")

        button_click_count = 0

        return

    

    # キュー移動モード

    if moving_queue_item:

        try:

            item = queue_items[moving_item_index - 2]

            new_pos = selected_index - 2

            if new_pos >= 0:

                mpd_client.move(int(item['pos']), new_pos)

        except Exception as e:

            print(f"Error moving: {e}")

        moving_queue_item = False

        moving_item_index = -1

        update_display()

        return

    

    # アクションメニュー表示中

    if action_menu_visible:

        handle_action_menu_selection()

        update_display()

        return

    

    # メイン画面

    if current_screen == "main_menu":

        if selected_index == 0:  # ライブラリ

            current_screen = "library"

            library_path = ""

            library_items = get_library_items(library_path)

            selected_index = 0

        elif selected_index == 1:  # 再生中

            current_screen = "now_playing"

        elif selected_index == 2:  # 再生キュー

            current_screen = "queue"

            queue_items = get_queue_items()

            selected_index = 0

        elif selected_index == 3:  # シャットダウン

            shutdown_system()

            return

        elif selected_index == 4:  # 再起動

            reboot_system()

            return

        elif selected_index == 5:  # 消灯

            set_backlight(False)

            return

        elif selected_index == 6:  # WiFi

            toggle_wifi()

            update_display()

            return

    

    # ライブラリ画面

    elif current_screen == "library":

        if selected_index < len(library_items):

            item = library_items[selected_index]

            

            if item['type'] == 'directory':

                menu_stack.append((library_path, selected_index))

                library_path = item['path']

                library_items = get_library_items(library_path)

                selected_index = 0

            else:

                show_action_menu(item)

    

    # キュー画面

    elif current_screen == "queue":

        if selected_index == 0:  # シャッフル

            try:

                status = mpd_client.status()

                current = status.get('random', '0') == '1'

                mpd_client.random(0 if current else 1)

            except Exception as e:

                print(f"Error toggling shuffle: {e}")

        elif selected_index == 1:  # リピート

            try:

                status = mpd_client.status()

                current = status.get('repeat', '0') == '1'

                mpd_client.repeat(0 if current else 1)

            except Exception as e:

                print(f"Error toggling repeat: {e}")

        else:

            show_action_menu(queue_items[selected_index - 2])

    

    update_display()



def handle_button_back(bt):

    """戻るボタン処理"""

    global current_screen, selected_index, library_path, library_items

    global menu_stack, action_menu_visible, screen_off

    

    # 消灯中の場合は無視

    if screen_off:

        return

    

    if action_menu_visible:

        action_menu_visible = False

    elif current_screen == "library":

        if menu_stack:

            library_path, selected_index = menu_stack.pop()

            library_items = get_library_items(library_path)

        else:

            current_screen = "main_menu"

            selected_index = 0

    elif current_screen in ["now_playing", "queue"]:

        current_screen = "main_menu"

        selected_index = 0

    

    update_display()



def handle_button_up(bt):

    """上ボタン処理"""

    global selected_index, action_menu_index, screen_off

    

    # 消灯中の場合は無視

    if screen_off:

        return

    

    if current_screen == "now_playing":

        # 音量アップ

        try:

            status = mpd_client.status()

            current_vol = int(status.get('volume', 50))

            new_vol = min(100, current_vol + 5)

            mpd_client.setvol(new_vol)

        except Exception as e:

            print(f"Error changing volume: {e}")

    elif action_menu_visible:

        action_menu_index = max(0, action_menu_index - 1)

    else:

        selected_index = max(0, selected_index - 1)

    

    update_display()



def handle_button_down(bt):

    """下ボタン処理"""

    global selected_index, action_menu_index, screen_off

    

    # 消灯中の場合は無視

    if screen_off:

        return

    

    if current_screen == "now_playing":

        # 音量ダウン

        try:

            status = mpd_client.status()

            current_vol = int(status.get('volume', 50))

            new_vol = max(0, current_vol - 5)

            mpd_client.setvol(new_vol)

        except Exception as e:

            print(f"Error changing volume: {e}")

    elif action_menu_visible:

        action_menu_index = min(len(action_menu_items) - 1, action_menu_index + 1)

    else:

        max_index = 0

        if current_screen == "main_menu":

            max_index = 6  # 7項目(0-6)

        elif current_screen == "library":

            max_index = len(library_items) - 1

        elif current_screen == "queue":

            max_index = len(queue_items) + 1

        

        selected_index = min(max_index, selected_index + 1)

    

    update_display()



def format_time(seconds):

    """秒を MM:SS 形式に変換"""

    minutes = int(seconds // 60)

    secs = int(seconds % 60)

    return f"{minutes:02d}:{secs:02d}"



def get_album_art(file_path):

    """アルバムアートを取得（MPDの埋め込みアートワークを使用）"""

    try:

        # MPDから埋め込みアートワークを取得

        albumart = mpd_client.albumart(file_path)

        if albumart and 'binary' in albumart:

            from io import BytesIO

            art_data = albumart['binary']

            return Image.open(BytesIO(art_data))

    except Exception as e:

        # albumartコマンドが失敗した場合、readpictureを試す

        try:

            picture = mpd_client.readpicture(file_path)

            if picture and 'binary' in picture:

                from io import BytesIO

                art_data = picture['binary']

                return Image.open(BytesIO(art_data))

        except Exception as e2:

            print(f"Error loading embedded album art: {e2}")

        

        # 埋め込みアートワークがない場合、cover.jpgを探す

        try:

            dir_path = os.path.dirname(file_path)

            music_dir = mpd_client.config().get('music_directory', '/var/lib/mpd/music')

            cover_path = os.path.join(music_dir, dir_path, "cover.jpg")

            

            if os.path.exists(cover_path):

                return Image.open(cover_path)

        except Exception as e3:

            print(f"Error loading cover.jpg: {e3}")

    

    return None



def update_display():

    """ディスプレイを更新"""

    draw.rectangle((0, 0, disp.width, disp.height), (0, 0, 0))

    

    if current_screen == "main_menu":

        draw_main_menu()

    elif current_screen == "library":

        draw_library()

    elif current_screen == "now_playing":

        draw_now_playing()

    elif current_screen == "queue":

        draw_queue()

    

    if action_menu_visible:

        draw_action_menu()

    

    disp.display(img)



def draw_main_menu():

    """メインメニューを描画"""

    wifi_status = "ON" if get_wifi_status() else "OFF"

    menu_items = [

        "ライブラリ", 

        "再生中", 

        "再生キュー",

        "シャットダウン",

        "再起動",

        "消灯",

        f"WiFi ({wifi_status})"

    ]

    line_height = 16  # 行間0px

    

    for i, item in enumerate(menu_items):

        y = i * line_height

        if i == selected_index:

            draw.rectangle([0, y, disp.width, y + line_height], fill=(255, 255, 255))

            draw.text((2, y), item, font=font, fill=(0, 0, 0), spacing=0)

        else:

            draw.text((2, y), item, font=font, fill=(255, 255, 255), spacing=0)



def draw_library():

    """ライブラリを描画"""

    line_height = 16  # 行間0px

    max_lines = 14

    start_idx = max(0, selected_index - max_lines // 2)

    

    for i in range(start_idx, min(len(library_items), start_idx + max_lines)):

        yi = i - start_idx

        y = yi * line_height

        

        item = library_items[i]

        prefix = "＞" if item['type'] == 'directory' else ""

        name = prefix + item['name']

        

        if i == selected_index:

            draw.rectangle([0, y, disp.width, y + line_height], fill=(255, 255, 255))

            draw.text((2, y), name[:40], font=font_small, fill=(0, 0, 0), spacing=0)

        else:

            draw.text((2, y), name[:40], font=font_small, fill=(255, 255, 255), spacing=0)



def draw_now_playing():

    """再生中画面を描画"""

    status = get_current_status()

    

    if status:

        # アルバムアート（背景）

        art = get_album_art(status['file'])

        if art:

            art = art.resize((disp.width, disp.height))

            img.paste(art, (0, 0))

            # 半透明オーバーレイ

            overlay = Image.new('RGBA', (disp.width, disp.height), (0, 0, 0, 32))

            img.paste(overlay, (0, 0), overlay)

        

        # 再生時間

        elapsed_str = format_time(status['elapsed'])

        duration_str = format_time(status['duration'])

        time_text = f"{elapsed_str} / {duration_str}"

        draw.text((10, disp.height - 32), time_text, font=font_small, fill=(255, 255, 255))

        

        # ステータス

        state_text = "再生中" if status['state'] == 'play' else "停止中"

        state_bbox = draw.textbbox((0, 0), state_text, font=font_small)

        state_width = state_bbox[2] - state_bbox[0]

        draw.text((disp.width - state_width - 10, disp.height - 32), 

                 state_text, font=font_small, fill=(255, 255, 255))

        

        # トラック情報

        info = f"{status['album']} - {status['title']} - {status['artist']}"

        info_bbox = draw.textbbox((0, 0), info[:40], font=font_small)

        info_width = info_bbox[2] - info_bbox[0]

        draw.text(((disp.width - info_width) // 2, disp.height - 16), 

                 info[:40], font=font_small, fill=(255, 255, 255))



def draw_queue():

    """再生キューを描画"""

    line_height = 16  # 行間0px

    max_lines = 14

    status = get_current_status()

    

    # 特殊項目

    shuffle_text = f"シャッフル再生 ({'ON' if status and status['random'] else 'OFF'})"

    repeat_text = f"リピート再生 ({'ON' if status and status['repeat'] else 'OFF'})"

    

    all_items = [shuffle_text, repeat_text] + [item['name'] for item in queue_items]

    

    start_idx = max(0, selected_index - max_lines // 2)

    

    for i in range(start_idx, min(len(all_items), start_idx + max_lines)):

        yi = i - start_idx

        y = yi * line_height

        

        if i == selected_index:

            draw.rectangle([0, y, disp.width, y + line_height], fill=(255, 255, 255))

            draw.text((2, y), all_items[i][:40], font=font_small, fill=(0, 0, 0), spacing=0)

        else:

            draw.text((2, y), all_items[i][:40], font=font_small, fill=(255, 255, 255), spacing=0)



def draw_action_menu():

    """アクションメニューを描画"""

    menu_height = len(action_menu_items) * 35 + 20

    menu_y = (disp.height - menu_height) // 2

    

    draw.rectangle([20, menu_y, disp.width - 20, menu_y + menu_height], 

                  fill=(50, 50, 50), outline=(255, 255, 255))

    

    for i, item in enumerate(action_menu_items):

        y = menu_y + 10 + (i * 35)

        if i == action_menu_index:

            draw.rectangle([25, y, disp.width - 25, y + 30], fill=(255, 255, 255))

            draw.text((30, y + 5), item, font=font_small, fill=(0, 0, 0))

        else:

            draw.text((30, y + 5), item, font=font_small, fill=(255, 255, 255))



def init_buttons():

    """ボタンを初期化"""

    button_action.when_pressed = handle_button_action

    button_back.when_pressed = handle_button_back

    button_up.when_pressed = handle_button_up

    button_down.when_pressed = handle_button_down

def connect_mpd():
    """MPDに接続"""
    try:
        mpd_client.connect("localhost", 6600)
        print("MPD connected successfully")
        return True
    except Exception as e:
        print(f"MPD connection error: {e}")
        return False

def keep_alive_loop():

    """メインクライアントの接続状態を定期的に確認し、切断されていたら再接続する"""

    global mpd_client

    # 30秒ごとに接続を確認

    interval = 5

    

    while True:

        try:
            # mpd_client.ping() は、接続が正常ならTrueを返すか何も返さない
            # 接続が切断されていれば例外(ConnectionError/ProtocolError)が発生する
            mpd_client.ping()
            # print("Main client ping successful.") # デバッグ用
        except Exception as e:
            # 接続エラーやソケットエラーが発生した場合
            print(f"Main client keep-alive failed: {e}. Attempting reconnect...")
            try:
                # 既存の接続を確実に切断
                mpd_client.disconnect()
            except:
                pass
            try:
                # 再接続
                mpd_client.connect("localhost", 6600)
            except Exception as re_e:
                print(f"Main client reconnection failed: {re_e}.")
        time.sleep(interval)

# メイン処理

if __name__ == "__main__":

    # MPD接続

    if not connect_mpd():
        print("Failed to connect to MPD. Exiting.")
        sys.exit(1)

    

    # ディスプレイ初期化

    disp = st7789.ST7789(

        height=240,

        rotation=90,

        port=0,

        cs=st7789.BG_SPI_CS_FRONT,

        dc=9,

        backlight=0,

        spi_speed_hz=30 * 1000 * 1000,

        offset_left=0,

        offset_top=0,

    )

    

    disp.begin()

    WIDTH = disp.width

    HEIGHT = disp.height

    img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))

    draw = ImageDraw.Draw(img)

    font = ImageFont.truetype("/opt/pmpdp/misaki/misaki_gothic.ttf", 16)

    font_small = font

    

    # ボタン初期化

    gpio_thread = threading.Thread(target=init_buttons)

    gpio_thread.start()

    

    # バックライトを点灯

    set_backlight(True)

    

    # 初期表示

    update_display()

    # keepalive with mpd
    keep_alive_thread = threading.Thread(target=keep_alive_loop)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()
    

    # メインループ

    try:

        while True:

            if current_screen == "now_playing":

                update_display()

            time.sleep(5)

    except KeyboardInterrupt:

        print("\nShutting down...")

        mpd_client.close()

        mpd_client.disconnect()
