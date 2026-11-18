import 'package:flutter/material.dart';
import '../../widgets/adaptive_buttons.dart';

import '../../main.dart' show gpmApi;
import '../../theme/gpm_theme.dart';
import '../../widgets/gpm_logo.dart';

class GpmLoginScreen extends StatefulWidget {
  final VoidCallback onSignedIn;

  const GpmLoginScreen({super.key, required this.onSignedIn});

  @override
  State<GpmLoginScreen> createState() => _GpmLoginScreenState();
}

class _GpmLoginScreenState extends State<GpmLoginScreen> {
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _invitationController = TextEditingController();
  final _registrationPasswordController = TextEditingController();
  final _registrationPasswordConfirmationController = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  final _registrationFormKey = GlobalKey<FormState>();

  String? _role;
  bool? _registrationNationality;
  _AuthMode _authMode = _AuthMode.login;
  bool _isLoading = false;
  bool _obscurePassword = true;
  String? _error;
  String? _notice;

  _RoleOption get _selectedRole =>
      _roleOptions.firstWhere((option) => option.value == _role);

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _invitationController.dispose();
    _registrationPasswordController.dispose();
    _registrationPasswordConfirmationController.dispose();
    super.dispose();
  }

  void _selectRole(String role) {
    setState(() {
      _role = role;
      _registrationNationality = null;
      _authMode = _AuthMode.login;
      _error = null;
      _notice = null;
    });
  }

  void _changeRole() {
    setState(() {
      _role = null;
      _authMode = _AuthMode.login;
      _passwordController.clear();
      _error = null;
      _notice = null;
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

  Future<void> _submitRegistration() async {
    if (_role == null || !_registrationFormKey.currentState!.validate()) return;
    setState(() {
      _isLoading = true;
      _error = null;
      _notice = null;
    });
    final result = await gpmApi.registerWithInvitation(
      invitation: _invitationController.text,
      password: _registrationPasswordController.text,
      passwordConfirmation: _registrationPasswordConfirmationController.text,
      role: _role!,
      nationality: _registrationNationality,
    );
    if (!mounted) return;
    if (result['success'] == true) {
      final username = result['username']?.toString() ?? '';
      _usernameController.text = username;
      _passwordController.clear();
      _invitationController.clear();
      _registrationPasswordController.clear();
      _registrationPasswordConfirmationController.clear();
      _registrationNationality = null;
      setState(() {
        _isLoading = false;
        _authMode = _AuthMode.login;
        _notice =
            'Аккаунт $username создан. Введите выбранный пароль для входа.';
      });
      return;
    }
    setState(() {
      _isLoading = false;
      _error = result['error']?.toString() ?? 'Не удалось принять приглашение';
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: GpmColors.page,
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
                      constraints: const BoxConstraints(maxWidth: 460),
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
                                    color: Color(0x0F020617),
                                    blurRadius: 32,
                                    offset: Offset(0, 12),
                                  ),
                                ]
                              : null,
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            _GpmAuthHero(compact: _role != null),
                            Transform.translate(
                              offset: Offset.zero,
                              child: Container(
                                padding: const EdgeInsets.fromLTRB(
                                  20,
                                  16,
                                  20,
                                  32,
                                ),
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
          style: Theme.of(
            context,
          ).textTheme.headlineSmall?.copyWith(fontSize: 26),
        ),
        const SizedBox(height: 16),
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
          child: TextButton(
            onPressed: _isLoading ? null : _changeRole,
            child: const GpmButtonContent(
              icon: Icon(Icons.arrow_back),
              label: Text('Изменить роль'),
            ),
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
          style: Theme.of(
            context,
          ).textTheme.bodyMedium?.copyWith(color: GpmColors.graphite),
        ),
        const SizedBox(height: 20),
        if (_notice != null) ...[
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFFE6F4EA),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFF6AA875)),
            ),
            child: Text(_notice!),
          ),
          const SizedBox(height: 16),
        ],
        GpmSegmentedButton<_AuthMode>(
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
                  _notice = null;
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
          _buildInvitationRegistration(selectedRole),
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
                  tooltip: _obscurePassword
                      ? 'Показать пароль'
                      : 'Скрыть пароль',
                  onPressed: () =>
                      setState(() => _obscurePassword = !_obscurePassword),
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
            FilledButton(
              onPressed: _isLoading ? null : _submit,
              child: GpmButtonContent(
                icon: _isLoading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.login),
                label: const Text('Войти'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInvitationRegistration(_RoleOption role) {
    return Form(
      key: _registrationFormKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Регистрация по приглашению: ${role.shortTitle}',
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          const Text(
            'Получите одноразовый код у администратора тестирования. Роль и логин уже закреплены в приглашении.',
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _invitationController,
            decoration: const InputDecoration(
              labelText: 'Код приглашения',
              prefixIcon: Icon(Icons.vpn_key_outlined),
            ),
            autocorrect: false,
            enableSuggestions: false,
            validator: (value) => value == null || value.trim().length < 20
                ? 'Введите действующий код приглашения'
                : null,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _registrationPasswordController,
            decoration: const InputDecoration(
              labelText: 'Новый пароль',
              prefixIcon: Icon(Icons.lock_outline),
              helperText: 'Не менее 12 символов',
            ),
            obscureText: true,
            validator: (value) => value == null || value.length < 12
                ? 'Пароль должен содержать не менее 12 символов'
                : null,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _registrationPasswordConfirmationController,
            decoration: const InputDecoration(
              labelText: 'Повторите пароль',
              prefixIcon: Icon(Icons.lock_reset_outlined),
            ),
            obscureText: true,
            onFieldSubmitted: (_) => _submitRegistration(),
            validator: (value) => value != _registrationPasswordController.text
                ? 'Пароли не совпадают'
                : null,
          ),
          if (role.value == 'worker') ...[
            const SizedBox(height: 12),
            FormField<bool>(
              validator: (_) => _registrationNationality == null
                  ? 'Укажите гражданство'
                  : null,
              builder: (field) => Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('Гражданство РФ'),
                  const SizedBox(height: 8),
                  GpmSegmentedButton<bool>(
                    segments: const [
                      ButtonSegment(value: true, label: Text('Да')),
                      ButtonSegment(value: false, label: Text('Нет')),
                    ],
                    emptySelectionAllowed: true,
                    selected: _registrationNationality == null
                        ? <bool>{}
                        : {_registrationNationality!},
                    onSelectionChanged: _isLoading
                        ? null
                        : (values) {
                            setState(
                              () => _registrationNationality = values.isEmpty
                                  ? null
                                  : values.first,
                            );
                            field.didChange(_registrationNationality);
                          },
                  ),
                  if (field.hasError)
                    Text(
                      field.errorText!,
                      style: const TextStyle(color: GpmColors.red),
                    ),
                ],
              ),
            ),
          ],
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
          FilledButton(
            onPressed: _isLoading ? null : _submitRegistration,
            child: GpmButtonContent(
              icon: _isLoading
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.person_add_alt_1_outlined),
              label: const Text('Создать аккаунт'),
            ),
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
    description: 'Заказать исполнителей',
    icon: Icons.business_center_outlined,
  ),
  _RoleOption(
    value: 'worker',
    title: 'Исполнитель',
    shortTitle: 'исполнитель',
    description: 'Найти работу и смены',
    icon: Icons.engineering_outlined,
  ),
  _RoleOption(
    value: 'logist',
    title: 'Логист',
    shortTitle: 'логист',
    description: 'Управлять заявками и командой',
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
        side: const BorderSide(color: GpmColors.softLine),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 40,
                height: 40,
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
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      option.description,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: GpmColors.graphite,
                        fontSize: 12,
                        height: 1.25,
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
  final bool compact;
  const _GpmAuthHero({required this.compact});

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width > 520;
    return Container(
      padding: EdgeInsets.fromLTRB(20, compact ? 12 : 24, 20, compact ? 4 : 8),
      color: GpmColors.surface,
      child: Column(
        children: [
          GpmLogoImage(width: compact ? 160 : (wide ? 280 : 240)),
          if (!compact) ...[
            const SizedBox(height: 12),
            const Text(
              'Люди. Работа. Все в одном месте.',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 18,
                height: 1.3,
                fontWeight: FontWeight.w500,
                color: GpmColors.graphite,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _AuthBackdrop extends StatelessWidget {
  const _AuthBackdrop();
  @override
  Widget build(BuildContext context) => const ColoredBox(color: GpmColors.page);
}
