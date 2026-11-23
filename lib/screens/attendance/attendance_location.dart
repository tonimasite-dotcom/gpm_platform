import 'package:geolocator/geolocator.dart';

/// One foreground measurement per attendance action; no location stream.
Future<Map<String, dynamic>> readAttendanceLocation() async {
  try {
    if (!await Geolocator.isLocationServiceEnabled()) {
      return {'error': 'disabled'};
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      return {'error': 'denied'};
    }
    final position = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 12),
      ),
    );
    return {
      'lat': position.latitude,
      'lon': position.longitude,
      'accuracy': position.accuracy,
      'measured_at': position.timestamp.toUtc().toIso8601String(),
    };
  } catch (_) {
    return {'error': 'unavailable'};
  }
}
