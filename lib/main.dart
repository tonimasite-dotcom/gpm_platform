import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

import 'screens/client/client_home_screen.dart';
import 'screens/logist/logist_home_screen.dart';
import 'screens/worker/worker_home_screen.dart';
import 'services/bitrix24_service.dart';
import 'services/chat_service.dart';
import 'services/supabase_compat.dart';
import 'theme/gpm_theme.dart';

late Bitrix24Service bitrix24;
late SupabaseCompatibilityLayer supabase;
late ChatService chatService;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(fileName: '.env');

  bitrix24 = Bitrix24Service();
  supabase = SupabaseCompatibilityLayer(bitrix24);
  chatService = ChatService();

  runApp(const GpmApp());
}

class GpmApp extends StatelessWidget {
  const GpmApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GPM Платформа',
      theme: buildGpmTheme(),
      home: const DevRoleSwitcher(),
    );
  }
}

enum DevRole {
  client('Клиент', Icons.business_center_outlined),
  worker('Исполнитель', Icons.engineering_outlined),
  logist('Логист', Icons.assignment_ind_outlined);

  const DevRole(this.label, this.icon);

  final String label;
  final IconData icon;
}

class DevRoleSwitcher extends StatefulWidget {
  const DevRoleSwitcher({super.key});

  @override
  State<DevRoleSwitcher> createState() => _DevRoleSwitcherState();
}

class _DevRoleSwitcherState extends State<DevRoleSwitcher> {
  DevRole _role = DevRole.logist;

  @override
  Widget build(BuildContext context) {
    final child = switch (_role) {
      DevRole.client => const ClientHomeScreen(),
      DevRole.worker => const WorkerHomeScreen(),
      DevRole.logist => const LogistHomeScreen(),
    };

    return Scaffold(
      backgroundColor: GpmColors.page,
      body: Column(
        children: [
          _GpmHeader(
            role: _role,
            onRoleChanged: (role) => setState(() => _role = role),
          ),
          Expanded(child: child),
        ],
      ),
    );
  }
}

class _GpmHeader extends StatelessWidget {
  final DevRole role;
  final ValueChanged<DevRole> onRoleChanged;

  const _GpmHeader({
    required this.role,
    required this.onRoleChanged,
  });

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
        decoration: const BoxDecoration(
          color: GpmColors.surface,
          border: Border(bottom: BorderSide(color: GpmColors.line)),
        ),
        child: Row(
          children: [
            const _GpmLogo(),
            const SizedBox(width: 18),
            Expanded(
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: SegmentedButton<DevRole>(
                  segments: DevRole.values
                      .map(
                        (role) => ButtonSegment<DevRole>(
                          value: role,
                          icon: Icon(role.icon),
                          label: Text(role.label),
                        ),
                      )
                      .toList(),
                  selected: {role},
                  onSelectionChanged: (selection) {
                    onRoleChanged(selection.first);
                  },
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _GpmLogo extends StatelessWidget {
  const _GpmLogo();

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: GpmColors.red,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: GpmColors.black, width: 2),
          ),
          child: const Icon(Icons.engineering, color: Colors.white, size: 30),
        ),
        const SizedBox(width: 8),
        const Text(
          'GPM',
          style: TextStyle(
            color: GpmColors.black,
            fontSize: 34,
            fontWeight: FontWeight.w900,
          ),
        ),
      ],
    );
  }
}
