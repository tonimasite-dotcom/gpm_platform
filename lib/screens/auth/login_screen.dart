import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi;
import '../../theme/gpm_theme.dart';

class GpmLoginScreen extends StatefulWidget {
  final VoidCallback onSignedIn;

  const GpmLoginScreen({super.key, required this.onSignedIn});

  @override
  State<GpmLoginScreen> createState() => _GpmLoginScreenState();
}

class _GpmLoginScreenState extends State<GpmLoginScreen> {
  final _usernameController = TextEditingController(text: 'admin');
  final _passwordController = TextEditingController();
  final _formKey = GlobalKey<FormState>();

  String? _role;
  _AuthMode _authMode = _AuthMode.login;
  bool _isLoading = false;
  bool _obscurePassword = true;
  String? _error;

  _RoleOption get _selectedRole =>
      _roleOptions.firstWhere((option) => option.value == _role);

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _selectRole(String role) {
    setState(() {
      _role = role;
      _authMode = _AuthMode.login;
      _error = null;
    });
  }

  void _changeRole() {
    setState(() {
      _role = null;
      _authMode = _AuthMode.login;
      _passwordController.clear();
      _error = null;
    });
  }

  Future<void> _submit() async {
    if (_role == null || !_formKey.currentState!.validate()) return;
    setState(() {
      _isLoading = true;
      _error = null;
    });

    final result = await gpmApi.login(
      username: _usernameController.text,
      password: _passwordController.text,
      role: _role!,
    );

    if (!mounted) return;
    setState(() {
      _isLoading = false;
      _error = result['success'] == true
          ? null
          : result['error']?.toString() ?? 'Не удалось войти';
    });
    if (result['success'] == true) widget.onSignedIn();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: GpmColors.page,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) => SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: constraints.maxHeight - 40),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 480),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const _GpmAuthLogo(),
                      const SizedBox(height: 28),
                      AnimatedSwitcher(
                        duration: const Duration(milliseconds: 180),
                        child: _role == null
                            ? _buildRoleSelection()
                            : _buildAuthentication(),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildRoleSelection() {
    return Column(
      key: const ValueKey('role-selection'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Выберите роль',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 20),
        for (final option in _roleOptions) ...[
          _RoleCard(option: option, onTap: () => _selectRole(option.value)),
          if (option != _roleOptions.last) const SizedBox(height: 10),
        ],
      ],
    );
  }

  Widget _buildAuthentication() {
    final selectedRole = _selectedRole;
    return Column(
      key: ValueKey('authentication-${selectedRole.value}'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: _isLoading ? null : _changeRole,
            icon: const Icon(Icons.arrow_back),
            label: const Text('Изменить роль'),
          ),
        ),
        const SizedBox(height: 6),
        Row(
          children: [
            Icon(selectedRole.icon, color: GpmColors.red),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                selectedRole.title,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          selectedRole.description,
          style: Theme.of(context)
              .textTheme
              .bodyMedium
              ?.copyWith(color: GpmColors.graphite),
        ),
        const SizedBox(height: 20),
        SegmentedButton<_AuthMode>(
          segments: const [
            ButtonSegment(
              value: _AuthMode.login,
              icon: Icon(Icons.login),
              label: Text('Вход'),
            ),
            ButtonSegment(
              value: _AuthMode.registration,
              icon: Icon(Icons.person_add_alt_1_outlined),
              label: Text('Регистрация'),
            ),
          ],
          selected: {_authMode},
          showSelectedIcon: false,
          onSelectionChanged: _isLoading
              ? null
              : (selection) => setState(() {
                    _authMode = selection.first;
                    _error = null;
                  }),
        ),
        const SizedBox(height: 20),
        if (_authMode == _AuthMode.login)
          _buildLoginForm()
        else
          _buildRegistrationNotice(selectedRole),
      ],
    );
  }

  Widget _buildLoginForm() {
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextFormField(
            controller: _usernameController,
            decoration: const InputDecoration(
              labelText: 'Логин',
              prefixIcon: Icon(Icons.person_outline),
            ),
            textInputAction: TextInputAction.next,
            validator: (value) => value == null || value.trim().isEmpty
                ? 'Введите логин'
                : null,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _passwordController,
            obscureText: _obscurePassword,
            decoration: InputDecoration(
              labelText: 'Пароль',
              prefixIcon: const Icon(Icons.lock_outline),
              suffixIcon: IconButton(
                tooltip: _obscurePassword
                    ? 'Показать пароль'
                    : 'Скрыть пароль',
                onPressed: () => setState(
                  () => _obscurePassword = !_obscurePassword,
                ),
                icon: Icon(
                  _obscurePassword
                      ? Icons.visibility_outlined
                      : Icons.visibility_off_outlined,
                ),
              ),
            ),
            onFieldSubmitted: (_) => _submit(),
            validator: (value) => value == null || value.isEmpty
                ? 'Введите пароль'
                : null,
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(
              _error!,
              style: const TextStyle(
                color: GpmColors.red,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
          const SizedBox(height: 18),
          FilledButton.icon(
            onPressed: _isLoading ? null : _submit,
            icon: _isLoading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.login),
            label: const Text('Войти'),
          ),
        ],
      ),
    );
  }

  Widget _buildRegistrationNotice(_RoleOption role) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: GpmColors.surface,
        border: Border.all(color: GpmColors.line),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        children: [
          const Icon(Icons.construction_outlined,
              size: 38, color: GpmColors.red),
          const SizedBox(height: 12),
          Text(
            'Регистрация: ${role.shortTitle}',
            textAlign: TextAlign.center,
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          const Text(
            'Самостоятельная регистрация пока готовится. '
            'На этапе тестирования используйте вход admin/admin.',
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

enum _AuthMode { login, registration }

class _RoleOption {
  final String value;
  final String title;
  final String shortTitle;
  final String description;
  final IconData icon;

  const _RoleOption({
    required this.value,
    required this.title,
    required this.shortTitle,
    required this.description,
    required this.icon,
  });
}

const _roleOptions = [
  _RoleOption(
    value: 'client',
    title: 'Клиент',
    shortTitle: 'клиент',
    description:
        'Создаёт заявки, следит за выполнением и общается с логистом.',
    icon: Icons.business_center_outlined,
  ),
  _RoleOption(
    value: 'worker',
    title: 'Исполнитель',
    shortTitle: 'исполнитель',
    description:
        'Выбирает доступные заказы, откликается на работу и получает выплаты.',
    icon: Icons.engineering_outlined,
  ),
  _RoleOption(
    value: 'logist',
    title: 'Логист',
    shortTitle: 'логист',
    description:
        'Управляет заявками, назначает исполнителей и контролирует работу.',
    icon: Icons.assignment_ind_outlined,
  ),
];

class _RoleCard extends StatelessWidget {
  final _RoleOption option;
  final VoidCallback onTap;

  const _RoleCard({required this.option, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: GpmColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: GpmColors.line),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: GpmColors.red.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(option.icon, color: GpmColors.red),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      option.title,
                      style: Theme.of(context)
                          .textTheme
                          .titleMedium
                          ?.copyWith(fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      option.description,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: GpmColors.graphite,
                            height: 1.35,
                          ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              const Padding(
                padding: EdgeInsets.only(top: 10),
                child: Icon(Icons.arrow_forward_ios, size: 16),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _GpmAuthLogo extends StatelessWidget {
  const _GpmAuthLogo();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Image.network(
          'assets/assets/images/gpm_logo.png?v=gpm-auth-logo-2',
          width: 56,
          height: 56,
          fit: BoxFit.contain,
          errorBuilder: (context, error, stackTrace) => Container(
            width: 56,
            height: 56,
            decoration: const BoxDecoration(
              color: GpmColors.red,
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.engineering,
              color: Colors.white,
              size: 32,
            ),
          ),
        ),
        const SizedBox(width: 10),
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
