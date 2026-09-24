<?php
/**
 * Plugin Name: MOTGU Rank Math Read-only Bridge
 * Description: Fixed, authenticated, read-only Rank Math inspection endpoints for ContentEngine.
 * Version: 0.1.0
 * Requires at least: 7.1
 * Requires PHP: 7.4
 * Author: MOTGU
 */

defined( 'ABSPATH' ) || exit;

require_once __DIR__ . '/src/Bridge.php';

\MOTGU\ContentEngine\RankMathBridge\Bridge::bootstrap();
