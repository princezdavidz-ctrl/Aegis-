abstract interface class RealtimeGateway {
  Stream<Map<String, Object?>> get events;
  Future<void> connect();
  Future<void> disconnect();
}
