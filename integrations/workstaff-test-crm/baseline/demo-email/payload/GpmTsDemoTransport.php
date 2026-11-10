<?php
namespace App\Services\Release;

/** Also stops callers that invoke Swift directly, without Laravel mail events. */
final class GpmTsDemoTransport implements \Swift_Transport
{
    public function isStarted() { return false; }
    public function start() { GpmTsDemoPolicy::assertContext(); }
    public function stop() {}
    public function ping() { GpmTsDemoPolicy::assertContext(); return true; }
    public function send(\Swift_Mime_SimpleMessage $message, &$failedRecipients = null)
    {
        GpmTsDemoPolicy::suppress('mail');
        return 0;
    }
    public function registerPlugin(\Swift_Events_EventListener $plugin) {}
}
