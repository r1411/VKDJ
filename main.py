import os
import json
from collections import deque
import threading
import time
from pathlib import Path
from random import randint
import wget
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from pygame import mixer

VK_TOKEN = None
VK_V = None
VK_GROUP = None
VK_ADMINS = None
SONG_DURATION_LIMIT = None
CLEAR_SONGS = None
ANY_MANAGE = None
ANY_PUSH_TOP = None

WORKDIR = Path(__file__).parent.resolve()
SONG_QUEUE = deque()
DOWNLOAD_QUEUE = deque()
CURRENT_SONG = None
PAUSED = False
FLAG_CLEARING = False

def load_json_file(filename):
	with open(filename, encoding='utf-8') as json_file:
		data = json.load(json_file)
		return data

def init_config():
	global VK_TOKEN, VK_V, VK_GROUP, VK_ADMINS, SONG_DURATION_LIMIT, CLEAR_SONGS, ANY_MANAGE, ANY_PUSH_TOP
	config = load_json_file(f'{WORKDIR}/config.json')
	VK_TOKEN = config['vk_token']
	VK_V = config['vk_v']
	VK_GROUP = config['vk_group_id']
	VK_ADMINS = config['vk_admin_ids']
	SONG_DURATION_LIMIT = config['song_duration_limit_seconds']
	CLEAR_SONGS = config['clear_saved_songs']
	ANY_MANAGE = config['allow_anybody_to_manage']
	ANY_PUSH_TOP = config['allow_anybody_to_push_top']

def clear_saved_songs():
	for f in os.listdir(f'{WORKDIR}/saved_songs'):
		try:
			os.remove(os.path.join(f'{WORKDIR}/saved_songs', f))
		except (PermissionError, IsADirectoryError, FileNotFoundError) as e:
			pass

def download_worker():
	global FLAG_CLEARING

	while True:
		while len(DOWNLOAD_QUEUE) == 0:
			time.sleep(0.1)
		
		audio = DOWNLOAD_QUEUE.popleft()
		song_name = f"{audio['owner_id']}_{audio['id']}.mp3" 
		song_path = f"{WORKDIR}/saved_songs/{song_name}"

		# Prevent downloading file if songs were cleared
		if FLAG_CLEARING:
			time.sleep(0.5)
			FLAG_CLEARING = False
			continue

		if not os.path.isfile(song_path):
			wget.download(audio['url'], song_path, bar=None)

		# Prevent adding downloaded file if songs were cleared 
		if FLAG_CLEARING:
			time.sleep(0.5)
			FLAG_CLEARING = False
			continue

		audio['localpath'] = song_path
		
		if audio['top']:
			SONG_QUEUE.appendleft(audio)
		else:
			SONG_QUEUE.append(audio)


def media_player_worker():
	global CURRENT_SONG, PAUSED

	mixer.init()
	print('Mixer initialized')
	while True:
		while len(SONG_QUEUE) == 0 or PAUSED:
			time.sleep(0.1)

		item = SONG_QUEUE.popleft()
		CURRENT_SONG = item
		print(f">>> Playing {item['artist']} — {item['title']}")
		mixer.music.load(item['localpath'])
		mixer.music.play()
		while mixer.music.get_busy() or PAUSED:
			time.sleep(0.1)

def process_messages(api, longpoll):
	global PAUSED, FLAG_CLEARING, CURRENT_SONG

	for event in longpoll.listen():
		if event.type == VkBotEventType.MESSAGE_NEW and event.obj.message:      
			msg = event.obj.message

			if msg['text'].lower() == '/whoami':
				api.messages.send(peer_id=msg['peer_id'], message=f"You are {'admin' if msg['from_id'] in VK_ADMINS else 'user'}", random_id=randint(2, 9999999))
				continue

			if msg['text'].lower() == '/queue' or msg['text'].lower() == '/list':
				if len(SONG_QUEUE) == 0:
					api.messages.send(peer_id=msg['peer_id'], message="No songs in queue", random_id=randint(2, 9999999))
					continue
				
				cur_title = "Nothing"
				if CURRENT_SONG is not None:
					cur_title = f"{CURRENT_SONG['artist']} — {CURRENT_SONG['title']}"

				message = f"➡ Playing: {cur_title}\n"
				message += "Songs in queue:\n"
				i = 1
				for song in SONG_QUEUE:
					message += f"🕑 {i}. {song['artist']} — {song['title']}\n"
					i += 1
				api.messages.send(peer_id=msg['peer_id'], message=message, random_id=randint(2, 9999999))
				continue

			if msg['text'].lower() == '/skip':
				if msg['from_id'] in VK_ADMINS or ANY_MANAGE:
					if not mixer.music.get_busy():
						api.messages.send(peer_id=msg['peer_id'], message=f"Error: Song not playing", random_id=randint(2, 9999999))
						continue

					api.messages.send(peer_id=msg['peer_id'], message=f"Skipping {CURRENT_SONG['artist']} — {CURRENT_SONG['title']}", random_id=randint(2, 9999999))
					mixer.music.stop()
				else:
					api.messages.send(peer_id=msg['peer_id'], message="Error: You're not admin!", random_id=randint(2, 9999999))

				continue

			if msg['text'].lower().startswith('/rem') or msg['text'].lower().startswith('/del'):
				if msg['from_id'] in VK_ADMINS or ANY_MANAGE:
					parts = msg['text'].split()
					
					if len(parts) < 2:
						api.messages.send(peer_id=msg['peer_id'], message="Error: Specify index! (/remove <index>)", random_id=randint(2, 9999999))
						continue

					idx = parts[1]

					if not idx.isnumeric():
						api.messages.send(peer_id=msg['peer_id'], message="Error: Index should be a number!", random_id=randint(2, 9999999))
						continue

					idx = int(idx)

					if idx <= 0 or idx > len(SONG_QUEUE):
						api.messages.send(peer_id=msg['peer_id'], message="Error: Invalid index!", random_id=randint(2, 9999999))
						continue

					skipping = SONG_QUEUE[idx - 1]
					del SONG_QUEUE[idx - 1]
					api.messages.send(peer_id=msg['peer_id'], message=f"Removed {skipping['artist']} — {skipping['title']}", random_id=randint(2, 9999999))

				else:
					api.messages.send(peer_id=msg['peer_id'], message="Error: You're not admin!", random_id=randint(2, 9999999))

				continue

			if msg['text'].lower() == '/pause':
				if msg['from_id'] in VK_ADMINS or ANY_MANAGE:
					if PAUSED:
						PAUSED = False
						mixer.music.unpause()
					else:
						PAUSED = True
						mixer.music.pause()
				else:
					api.messages.send(peer_id=msg['peer_id'], message="Error: You're not admin!", random_id=randint(2, 9999999))

				continue

			if msg['text'].lower() == '/resume':
				if msg['from_id'] in VK_ADMINS or ANY_MANAGE:
					if PAUSED:
						PAUSED = False
						mixer.music.unpause()
				else:
					api.messages.send(peer_id=msg['peer_id'], message="Error: You're not admin!", random_id=randint(2, 9999999))

				continue

			if msg['text'].lower() == '/song':
				if CURRENT_SONG is None:
					api.messages.send(peer_id=msg['peer_id'], message="No song has been played yet", random_id=randint(2, 9999999))
					continue

				api.messages.send(peer_id=msg['peer_id'], message=f"Song: {CURRENT_SONG['artist']} — {CURRENT_SONG['title']}", random_id=randint(2, 9999999))

				continue

			if msg['text'].lower() == '/clear':
				if msg['from_id'] in VK_ADMINS or ANY_MANAGE:
					
					FLAG_CLEARING = True
					DOWNLOAD_QUEUE.clear()
					SONG_QUEUE.clear()
					CURRENT_SONG = None

					mixer.music.stop()
					mixer.music.unload()
					
					if CLEAR_SONGS:
						clear_saved_songs()
						print('Saved songs cleared')

					api.messages.send(peer_id=msg['peer_id'], message=f"Cleared all songs", random_id=randint(2, 9999999))

					continue
				else:
					api.messages.send(peer_id=msg['peer_id'], message="Error: You're not admin!", random_id=randint(2, 9999999))

			if msg['text'].lower() == '/help':
				message = "Bot commands list:\n"
				message += "/queue, /list - Show songs list\n"
				message += "/rem <idx>, /del <idx> - Remove song in queue by index\n"
				message += "/skip - Skip current song\n"
				message += "/pause - Pause / resume current song\n"
				message += "/song - Show latest song\n"
				message += "/clear - Clear songs queue\n"
				message += "/top - Put attached audios on top of the queue\n"
				message += "/help - Show this message\n"
				api.messages.send(peer_id=msg['peer_id'], message=message, random_id=randint(2, 9999999))

				continue


			if len(msg['attachments']) == 0:
				api.messages.send(peer_id=msg['peer_id'], message='Error: No audio attached', random_id=randint(2, 9999999))
				continue

			suitable_attachments = []

			for attachment in msg['attachments']:
				if not 'type' in attachment:
					continue

				if attachment['type'] != 'audio':
					continue

				if not 'audio' in attachment:
					continue

				if attachment['audio']['duration'] > SONG_DURATION_LIMIT:
					continue

				if not attachment['audio']['url']:
					continue
				
				push_on_top = False
				if msg['text'].lower() == '/top':
					if msg['from_id'] in VK_ADMINS or ANY_PUSH_TOP:
						push_on_top = True

				attachment['audio']['top'] = push_on_top

				suitable_attachments.append(attachment['audio'])

			if len(suitable_attachments) == 0:
				api.messages.send(peer_id=msg['peer_id'], message='Error: No valid audio attached', random_id=randint(2, 9999999))
			else:
				FLAG_CLEARING = False
				DOWNLOAD_QUEUE.extend(suitable_attachments)
				api.messages.send(peer_id=msg['peer_id'], message=f'Adding {len(suitable_attachments)} track{"s" if len(suitable_attachments) > 1 else ""} to playlist.', random_id=randint(2, 9999999))


def main():
	# Initialize global varriables
	init_config()

	# Setting up directories
	print(f'Working directory: {WORKDIR}')
	Path(f'{WORKDIR}/saved_songs').mkdir(exist_ok=True)
	if CLEAR_SONGS:
		clear_saved_songs()
		print('Saved songs cleared')

	# Starting audio player thread
	threading.Thread(target=media_player_worker, daemon=False).start()

	# Starting donwloader thread
	threading.Thread(target=download_worker, daemon=False).start()

	# Starting VK longpoll bot
	vk_session = vk_api.VkApi(token=VK_TOKEN, api_version=VK_V)
	vk_group_api = vk_session.get_api()
	vk_longpoll = VkBotLongPoll(vk_session, VK_GROUP)

	print('Listening to messages now. Ctrl + Pause/Break to stop.')
	process_messages(vk_group_api, vk_longpoll)


if __name__ == '__main__':
	main()
