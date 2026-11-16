<?php
namespace App\Services\Release;

use Symfony\Component\Mailer\Envelope;
use Symfony\Component\Mailer\SentMessage;
use Symfony\Component\Mailer\Transport\TransportInterface;
use Symfony\Component\Mime\RawMessage;

/** No recipient, body, credential or code is read or logged. */
final class GpmTsDemoTransport implements TransportInterface
{
    public function send(RawMessage $message, ?Envelope $envelope = null): ?SentMessage
    {
        GpmTsDemoPolicy::suppress('mail');
        return null;
    }

    public function __toString(): string
    {
        return 'gpm-ts-demo://null';
    }
}
