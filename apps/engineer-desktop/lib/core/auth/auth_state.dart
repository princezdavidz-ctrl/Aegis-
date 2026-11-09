enum AuthStatus { unknown, signedOut, signedIn, expired }

class AuthState {
  const AuthState({this.status = AuthStatus.unknown, this.displayName});
  final AuthStatus status;
  final String? displayName;
  bool get isAuthenticated => status == AuthStatus.signedIn;
}
