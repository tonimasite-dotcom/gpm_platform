"""Export only visible user/assistant dialogue and user image attachments."""
from pathlib import Path
import argparse
import base64
import hashlib
import json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', required=True)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    source = Path(args.session)
    destination = Path(args.destination)
    if destination.exists():
        raise RuntimeError('NEW_PRIVATE_TRANSCRIPT_DIRECTORY_REQUIRED')
    destination.mkdir(parents=True, mode=0o700)
    watermark = source.stat().st_size
    messages, images = [], {}
    last_timestamp = None
    thread = None
    with source.open('rb') as stream:
        consumed = 0
        while consumed < watermark:
            line = stream.readline()
            consumed += len(line)
            if not line.endswith(b'\n'):
                break
            record = json.loads(line)
            payload = record.get('payload', {})
            last_timestamp = record.get('timestamp', last_timestamp)
            if record.get('type') == 'session_meta':
                thread = payload.get('id')
            if record.get('type') == 'event_msg':
                kind = payload.get('type')
                if kind == 'user_message' or (kind == 'agent_message' and payload.get('phase') in ['commentary', 'final_answer', 'final']):
                    messages.append({'timestamp': record.get('timestamp'), 'role': 'user' if kind == 'user_message' else 'assistant',
                                     'phase': payload.get('phase'), 'text': payload.get('message', '')})
            if record.get('type') == 'response_item' and payload.get('type') == 'message' and payload.get('role') == 'user':
                for part in payload.get('content', []):
                    url = part.get('image_url', '')
                    if isinstance(url, dict):
                        url = url.get('url', '')
                    if part.get('type') != 'input_image' or not isinstance(url, str) or not url.startswith('data:image/'):
                        continue
                    header, encoded = url.split(',', 1)
                    data = base64.b64decode(encoded, validate=True)
                    digest = hashlib.sha256(data).hexdigest()
                    if digest in images:
                        continue
                    suffix = '.png' if 'png' in header else '.jpg' if 'jpeg' in header else '.webp' if 'webp' in header else '.bin'
                    folder = destination / 'images'
                    folder.mkdir(exist_ok=True)
                    name = 'image-%02d' % (len(images) + 1) + suffix
                    (folder / name).write_bytes(data)
                    images[digest] = {'file': 'images/' + name, 'sha256': digest, 'bytes': len(data), 'timestamp': record.get('timestamp')}
    if not messages:
        raise RuntimeError('VISIBLE_MESSAGES_REQUIRED')
    with (destination / 'messages.jsonl').open('w', encoding='utf-8') as output:
        for item in messages:
            output.write(json.dumps(item, ensure_ascii=False) + '\n')
    lines = ['# Visible project conversation', '', 'Snapshot through: ' + str(last_timestamp), '']
    for i, item in enumerate(messages, 1):
        lines += ['## %d. %s — %s' % (i, item['role'], item['timestamp']), '', item['text'], '']
    for item in images.values():
        lines += ['![Attachment](' + item['file'] + ')', '']
    (destination / 'CHAT_TRANSCRIPT.md').write_text('\n'.join(lines), encoding='utf-8')
    metadata = {'thread_id': thread, 'source_byte_watermark': watermark, 'last_record_timestamp': last_timestamp,
                'user_messages': sum(item['role'] == 'user' for item in messages),
                'assistant_messages': sum(item['role'] == 'assistant' for item in messages), 'images': list(images.values()),
                'raw_session_copied': False, 'system_developer_or_reasoning_exported': False,
                'nonvisible_guardian_sessions_exported': False}
    (destination / 'export-metadata.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'visible_messages': len(messages), 'user_images': len(images), 'thread_id': thread}))


if __name__ == '__main__':
    main()
