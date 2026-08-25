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
  final _usernameController = TextEditingController();
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
      backgroundColor: const Color(0xFFEDE9E4),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final horizontalPadding = constraints.maxWidth > 520 ? 18.0 : 0.0;
          return Stack(
            children: [
              const Positioned.fill(child: _AuthBackdrop()),
              SafeArea(
                child: SingleChildScrollView(
                  padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
                  child: Center(
                    child: ConstrainedBox(
                      constraints: BoxConstraints(
                        maxWidth: 430,
                        minHeight: constraints.maxHeight,
                      ),
                      child: Container(
                        clipBehavior: Clip.antiAlias,
                        decoration: BoxDecoration(
                          color: GpmColors.page,
                          borderRadius: BorderRadius.circular(
                            constraints.maxWidth > 520 ? 28 : 0,
                          ),
                          boxShadow: constraints.maxWidth > 520
                              ? const [
                                  BoxShadow(
                                    color: Color(0x26000000),
                                    blurRadius: 32,
                                    offset: Offset(0, 12),
                                  ),
                                ]
                              : null,
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            const _GpmAuthHero(),
                            Transform.translate(
                              offset: const Offset(0, -18),
                              child: Container(
                                padding:
                                    const EdgeInsets.fromLTRB(20, 24, 20, 32),
                                decoration: const BoxDecoration(
                                  color: GpmColors.page,
                                  borderRadius: BorderRadius.vertical(
                                    top: Radius.circular(28),
                                  ),
                                ),
                                child: AnimatedSwitcher(
                                  duration: const Duration(milliseconds: 220),
                                  child: _role == null
                                      ? _buildRoleSelection()
                                      : _buildAuthentication(),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          );
        },
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
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontSize: 26,
              ),
        ),
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: const Color(0xFFFFF4D6),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: const Color(0xFFE0A800)),
          ),
          child: const Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.science_outlined, size: 20),
              SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Закрытое тестирование. Не вводите реальные паспортные, банковские и иные чувствительные данные.',
                ),
              ),
            ],
          ),
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
        const SizedBox(height: 10),
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
          style: ButtonStyle(
            minimumSize: const WidgetStatePropertyAll(Size(0, 48)),
            shape: WidgetStatePropertyAll(
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
          ),
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
    return AutofillGroup(
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextFormField(
              controller: _usernameController,
              autofillHints: const [AutofillHints.username],
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
              autofillHints: const [AutofillHints.password],
              obscureText: _obscurePassword,
              decoration: InputDecoration(
                labelText: 'Пароль',
                prefixIcon: const Icon(Icons.lock_outline),
                suffixIcon: IconButton(
                  tooltip:
                      _obscurePassword ? 'Показать пароль' : 'Скрыть пароль',
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
              validator: (value) =>
                  value == null || value.isEmpty ? 'Введите пароль' : null,
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
            'Для участия в закрытом тестировании запросите доступ у администратора GPM.',
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
    description: 'Создаёт заявки, следит за выполнением и общается с логистом.',
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
        borderRadius: BorderRadius.circular(18),
        side: const BorderSide(color: Color(0xFFE8E3E0)),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(17),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: GpmColors.red.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(14),
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
              Container(
                width: 30,
                height: 30,
                margin: const EdgeInsets.only(top: 8),
                decoration: BoxDecoration(
                  color: GpmColors.page,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.arrow_forward_ios, size: 14),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _GpmAuthHero extends StatelessWidget {
  const _GpmAuthHero();

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 220,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          const Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFFFFF8F3), Color(0xFFFFE9ED)],
                ),
              ),
            ),
          ),
          const Positioned(
            top: -42,
            right: -34,
            child: _DecorativeBubble(
              size: 150,
              color: Color(0x24F8B800),
            ),
          ),
          const Positioned(
            left: -50,
            bottom: -56,
            child: _DecorativeBubble(
              size: 150,
              color: Color(0x18FF1744),
            ),
          ),
          Positioned(
            top: 34,
            left: 28,
            child: Transform.rotate(
              angle: -0.16,
              child: Container(
                width: 42,
                height: 12,
                decoration: BoxDecoration(
                  color: GpmColors.yellow.withValues(alpha: 0.45),
                  borderRadius: BorderRadius.circular(99),
                ),
              ),
            ),
          ),
          Positioned(
            right: 34,
            bottom: 46,
            child: Container(
              width: 10,
              height: 10,
              decoration: const BoxDecoration(
                color: GpmColors.red,
                shape: BoxShape.circle,
              ),
            ),
          ),
          Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 92,
                  height: 92,
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: GpmColors.red.withValues(alpha: 0.14),
                        blurRadius: 24,
                        offset: const Offset(0, 8),
                      ),
                    ],
                  ),
                  child: Image.asset(
                    'assets/images/gpm_logo.png',
                    fit: BoxFit.contain,
                    errorBuilder: (context, error, stackTrace) => const Icon(
                      Icons.engineering,
                      color: GpmColors.red,
                      size: 54,
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                const Text(
                  'GPM',
                  style: TextStyle(
                    color: GpmColors.black,
                    fontSize: 30,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 1.2,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'Заказы, люди и работа в одном месте',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        fontSize: 12,
                        color: GpmColors.graphite.withValues(alpha: 0.68),
                      ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DecorativeBubble extends StatelessWidget {
  final double size;
  final Color color;

  const _DecorativeBubble({required this.size, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

class _AuthBackdrop extends StatelessWidget {
  const _AuthBackdrop();

  @override
  Widget build(BuildContext context) {
    return const DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFFF2EEE9), Color(0xFFE8E2DC)],
        ),
      ),
    );
  }
}
