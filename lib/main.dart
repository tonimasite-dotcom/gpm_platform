import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

import 'screens/auth/login_screen.dart';
import 'screens/client/client_home_screen.dart';
import 'screens/logist/logist_home_screen.dart';
import 'screens/worker/worker_home_screen.dart';
import 'services/gpm_api_service.dart';
import 'services/chat_service.dart';
import 'services/supabase_compat.dart';
import 'theme/gpm_theme.dart';

late GpmApiService gpmApi;
// Backward compatibility for older screens and examples.
late GpmApiService bitrix24;
late SupabaseCompatibilityLayer supabase;
late ChatService chatService;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    await dotenv.load(fileName: '.env');
  } catch (_) {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo');
  }

  gpmApi = GpmApiService();
  bitrix24 = gpmApi;
  supabase = SupabaseCompatibilityLayer(gpmApi);
  chatService = ChatService();

  runApp(const GpmApp());
}

class GpmApp extends StatefulWidget {
  const GpmApp({super.key});

  @override
  State<GpmApp> createState() => _GpmAppState();
}

class _GpmAppState extends State<GpmApp> {
  void _refreshSession() {
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GPM Платформа',
      theme: buildGpmTheme(),
      home: gpmApi.requiresAuth && !gpmApi.hasAuthSession
          ? GpmLoginScreen(onSignedIn: _refreshSession)
          : DevRoleSwitcher(onSignedOut: _refreshSession),
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
  final VoidCallback onSignedOut;

  const DevRoleSwitcher({
    super.key,
    required this.onSignedOut,
  });

  @override
  State<DevRoleSwitcher> createState() => _DevRoleSwitcherState();
}

class _DevRoleSwitcherState extends State<DevRoleSwitcher> {
  late DevRole _role;

  @override
  void initState() {
    super.initState();
    _role = DevRole.values.firstWhere(
      (role) => role.name == gpmApi.currentRole,
      orElse: () => DevRole.logist,
    );
  }

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
            onSignedOut: widget.onSignedOut,
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
  final VoidCallback onSignedOut;

  const _GpmHeader({
    required this.role,
    required this.onRoleChanged,
    required this.onSignedOut,
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
              child: gpmApi.requiresAuth
                  ? Align(
                      alignment: Alignment.centerLeft,
                      child: Chip(
                        avatar: Icon(role.icon, size: 18),
                        label: Text(role.label),
                      ),
                    )
                  : SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: SegmentedButton<DevRole>(
                        segments: DevRole.values
                            .map(
                              (item) => ButtonSegment<DevRole>(
                                value: item,
                                icon: Icon(item.icon),
                                label: Text(item.label),
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
            if (gpmApi.requiresAuth) ...[
              const SizedBox(width: 8),
              IconButton(
                tooltip: 'Выйти',
                onPressed: () {
                  gpmApi.logout();
                  onSignedOut();
                },
                icon: const Icon(Icons.logout),
              ),
            ],
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
        Image.asset(
          'assets/images/gpm_logo.png',
          width: 48,
          height: 48,
          fit: BoxFit.contain,
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
