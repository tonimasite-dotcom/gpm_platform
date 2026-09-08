import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/models/chat_models.dart';
import 'package:gpm_platform/services/chat_service.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';

class RecordingChatApi extends GpmApiService {
  int fetches = 0;
  String? requestedId;
  String? sentText;

  @override
  Future<Map<String, dynamic>> getMyChatConversation(String threadId) async {
    fetches++;
    return {
      'thread': {
        'id': threadId,
        'order_id': '001/26',
        'type': 'workerLogist',
        'title': 'Заявка № 001/26',
        'updated_at': '2026-09-08T12:00:00Z',
      },
      'messages': [
        {
          'id': 'server-message',
          'thread_id': threadId,
          'sender_role': 'worker',
          'sender_name': 'Другой исполнитель',
          'text': 'Сообщение',
          'created_at': '2026-09-08T12:00:00Z',
          'is_system': false,
          'is_own': false,
        },
      ],
    };
  }

  @override
  Future<Map<String, dynamic>> sendMyChatMessage(
    String threadId,
    String text, {
    String? clientMessageId,
  }) async {
    requestedId = clientMessageId;
    sentText = text;
    return {
      'message': {
        'id': clientMessageId,
        'thread_id': threadId,
        'sender_role': 'worker',
        'sender_name': 'Я',
        'text': text,
        'is_own': true,
        'created_at': '2026-09-08T12:00:01Z',
      },
    };
  }
}

void main() {
  setUp(() => dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n'));

  test(
    'conversation uses one API call and preserves server ownership',
    () async {
      final api = RecordingChatApi();
      final service = ChatService(api: api);
      final conversation = await service.getConversation(
        'chat-001/26-workerLogist',
      );
      expect(api.fetches, 1);
      expect(conversation.thread.title, 'Заявка № 001/26');
      expect(conversation.messages.single.isOwn, isFalse);
    },
  );

  test(
    'send returns acknowledgment directly and passes stable retry id',
    () async {
      final api = RecordingChatApi();
      final service = ChatService(api: api);
      final id = ChatService.newMessageId();
      final message = await service.sendMessage(
        threadId: 'chat-001/26-workerLogist',
        senderRole: ChatRole.worker,
        senderName: 'Я',
        text: '  Сообщение  ',
        clientMessageId: id,
      );
      expect(api.fetches, 0);
      expect(api.requestedId, id);
      expect(api.sentText, 'Сообщение');
      expect(message.id, id);
      expect(message.isOwn, isTrue);
    },
  );

  test(
    'outbox ids are unique UUIDs and drafts are separated by thread and role',
    () {
      final ids = List.generate(100, (_) => ChatService.newMessageId());
      expect(ids.toSet().length, ids.length);
      final uuid = RegExp(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
      );
      expect(ids.every(uuid.hasMatch), isTrue);
      final service = ChatService(api: RecordingChatApi());
      service.saveDraft('first', ChatRole.worker, 'Черновик');
      expect(service.draft('first', ChatRole.worker), 'Черновик');
      expect(service.draft('second', ChatRole.worker), isEmpty);
      expect(service.draft('first', ChatRole.logist), isEmpty);
    },
  );
}
