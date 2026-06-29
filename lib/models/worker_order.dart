class WorkerOrder {
  final String id;
  final String title;
  final String place;
  final String dateTime;
  final String duration;
  final String rate;
  final String total;
  final String paymentType;

  const WorkerOrder({
    required this.id,
    required this.title,
    required this.place,
    required this.dateTime,
    required this.duration,
    required this.rate,
    required this.total,
    required this.paymentType,
  });
}
