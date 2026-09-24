<?php

declare( strict_types=1 );

define( 'ABSPATH', __DIR__ );
define( 'MOTGU_RANK_MATH_BRIDGE_SECRET', '0123456789abcdef0123456789abcdef' );
define( 'MOTGU_RANK_MATH_BRIDGE_USER_ID', 42 );
define( 'RANK_MATH_VERSION', '1.0.279' );
define( 'RANK_MATH_PRO_VERSION', '3.0.119' );

$GLOBALS['bridge_routes'] = [];
$GLOBALS['bridge_abilities'] = [];
$GLOBALS['bridge_current_user'] = 0;
$GLOBALS['bridge_execution_count'] = 0;
$GLOBALS['rank_math_tracking_opt_in'] = false;

class WP_Error {
	private $code;
	private $message;
	private $data;

	public function __construct( $code = '', $message = '', $data = null ) {
		$this->code    = $code;
		$this->message = $message;
		$this->data    = $data;
	}

	public function get_error_code() {
		return $this->code;
	}

	public function get_error_message() {
		return $this->message;
	}

	public function get_error_data() {
		return $this->data;
	}
}

function is_wp_error( $value ) {
	return $value instanceof WP_Error;
}

class WP_REST_Server {
	const READABLE = 'GET';
}

class WP_REST_Request {
	private $method;
	private $route;
	private $headers;
	private $params;

	public function __construct( string $method, string $route, array $headers = [], array $params = [] ) {
		$this->method  = $method;
		$this->route   = $route;
		$this->headers = array_change_key_case( $headers, CASE_LOWER );
		$this->params  = $params;
	}

	public function get_method() {
		return $this->method;
	}

	public function get_route() {
		return $this->route;
	}

	public function get_header( $name ) {
		return $this->headers[ strtolower( $name ) ] ?? '';
	}

	public function get_param( $name ) {
		return $this->params[ $name ] ?? null;
	}
}

class WP_REST_Response {
	public $data;

	public function __construct( $data ) {
		$this->data = $data;
	}
}

class FakeTracking {
	public function is_opted_in() {
		return (bool) $GLOBALS['rank_math_tracking_opt_in'];
	}
}

function rank_math() {
	$runtime           = new stdClass();
	$runtime->tracking = new FakeTracking();
	return $runtime;
}

class FakeAbility {
	private $meta;
	private $result;
	public $executed = 0;

	public function __construct( array $meta, array $result ) {
		$this->meta   = $meta;
		$this->result = $result;
	}

	public function get_meta() {
		return $this->meta;
	}

	public function execute( $input ) {
		++$this->executed;
		++$GLOBALS['bridge_execution_count'];
		return $this->result;
	}
}

function add_action( $hook, $callback ) {}
function register_rest_route( $namespace, $route, $args ) {
	$GLOBALS['bridge_routes'][] = [ $namespace, $route, $args ];
}
function wp_get_ability( $name ) {
	return $GLOBALS['bridge_abilities'][ $name ] ?? null;
}
function get_post( $id ) {
	return $id > 0 ? (object) [ 'ID' => $id, 'post_status' => 'publish' ] : null;
}
function get_user_by( $field, $id ) {
	return (int) $id === 42 ? (object) [ 'ID' => 42 ] : false;
}
function get_current_user_id() {
	return (int) $GLOBALS['bridge_current_user'];
}
function wp_set_current_user( $id ) {
	$GLOBALS['bridge_current_user'] = (int) $id;
}
function current_user_can( $capability, ...$args ) {
	return true;
}
function get_permalink( $id ) {
	return 'https://motgu.test/post-' . $id . '/';
}
function get_post_modified_time( $format, $gmt, $id ) {
	return '2026-09-24T06:00:00Z';
}
function get_post_status( $id ) {
	return 'publish';
}
function wp_json_encode( $value ) {
	return json_encode( $value );
}
function rest_ensure_response( $value ) {
	return new WP_REST_Response( $value );
}

require_once dirname( __DIR__ ) . '/src/Bridge.php';

use MOTGU\ContentEngine\RankMathBridge\Bridge;

function expect_true( $condition, string $message ): void {
	if ( ! $condition ) {
		fwrite( STDERR, "FAIL: {$message}\n" );
		exit( 1 );
	}
}

function expect_error_code( $value, string $code, string $message ): void {
	expect_true( $value instanceof WP_Error, $message . ' (not WP_Error)' );
	expect_true(
		$value->get_error_code() === $code,
		$message . ' (unexpected code ' . $value->get_error_code() . ')'
	);
}

function readonly_meta(): array {
	return [
		'annotations' => [
			'readonly'    => true,
			'destructive' => false,
			'idempotent'  => true,
		],
	];
}

Bridge::register_routes();
expect_true( count( $GLOBALS['bridge_routes'] ) === 3, 'exactly three routes must be registered' );
$routes = array_map(
	static function ( $row ) {
		return $row[1];
	},
	$GLOBALS['bridge_routes']
);
expect_true(
	in_array( '/rank-math/posts/(?P<post_id>[1-9][0-9]*)/seo-meta', $routes, true ),
	'seo-meta route missing'
);
expect_true(
	in_array( '/rank-math/posts/(?P<post_id>[1-9][0-9]*)/schema', $routes, true ),
	'schema route missing'
);
expect_true(
	in_array( '/rank-math/posts/(?P<post_id>[1-9][0-9]*)/links', $routes, true ),
	'links route missing'
);
foreach ( $routes as $route ) {
	expect_true(
		strpos( $route, 'ability' ) === false && strpos( $route, 'capability' ) === false,
		'route must not accept arbitrary ability/capability'
	);
}

$GLOBALS['bridge_execution_count'] = 0;
$forbidden = Bridge::execute_allowed_ability( 'rank-math/set-module-status', [ 'post_id' => 5 ] );
expect_error_code(
	$forbidden,
	'motgu_rank_math_bridge_capability_forbidden',
	'write ability must fail closed'
);
expect_true( $GLOBALS['bridge_execution_count'] === 0, 'write ability must never execute' );

$GLOBALS['bridge_abilities']['rank-math/get-post-seo-meta'] = new FakeAbility(
	[
		'annotations' => [
			'readonly'    => false,
			'destructive' => false,
			'idempotent'  => true,
		],
	],
	[ 'post_id' => 5 ]
);
$unsafe = Bridge::execute_allowed_ability( 'rank-math/get-post-seo-meta', [ 'post_id' => 5 ] );
expect_error_code(
	$unsafe,
	'motgu_rank_math_bridge_ability_not_readonly',
	'allowed name with non-readonly runtime annotation must fail closed'
);
expect_true(
	$GLOBALS['bridge_abilities']['rank-math/get-post-seo-meta']->executed === 0,
	'non-readonly ability annotation must block execution'
);

$GLOBALS['bridge_abilities']['rank-math/get-post-seo-meta'] = new FakeAbility(
	readonly_meta(),
	[ 'post_id' => 5 ]
);
$GLOBALS['rank_math_tracking_opt_in'] = true;
$telemetry_blocked = Bridge::execute_allowed_ability( 'rank-math/get-post-seo-meta', [ 'post_id' => 5 ] );
expect_error_code(
	$telemetry_blocked,
	'motgu_rank_math_bridge_rank_math_tracking_enabled',
	'Rank Math usage telemetry opt-in must fail closed'
);
expect_true(
	$GLOBALS['bridge_abilities']['rank-math/get-post-seo-meta']->executed === 0,
	'telemetry opt-in must block ability execution'
);
$GLOBALS['rank_math_tracking_opt_in'] = false;

$GLOBALS['bridge_abilities']['rank-math/get-post-seo-meta'] = new FakeAbility(
	readonly_meta(),
	[
		'post_id'             => 5,
		'title'               => 'Safe title',
		'description'         => 'Safe description',
		'focus_keyword'       => 'oil painting',
		'robots'              => [ 'index', 'follow' ],
		'canonical'           => 'https://motgu.test/post-5/',
		'og_title'            => 'OG title',
		'og_description'      => 'OG description',
		'twitter_title'       => 'Twitter title',
		'twitter_description' => 'Twitter description',
		'seo_score'           => 82,
		'access_token'        => 'must-not-leak',
		'unknown_field'       => 'must-not-leak',
	]
);
$route     = '/motgu-contentengine/v1/rank-math/posts/5/seo-meta';
$timestamp = (string) time();
$signature = hash_hmac(
	'sha256',
	"GET\n{$route}\n{$timestamp}",
	MOTGU_RANK_MATH_BRIDGE_SECRET
);
$request = new WP_REST_Request(
	'GET',
	$route,
	[
		'x-motgu-bridge-timestamp' => $timestamp,
		'x-motgu-bridge-signature' => $signature,
	],
	[ 'post_id' => '5' ]
);
expect_true(
	Bridge::authorize_request( $request, 'seo-meta' ) === true,
	'valid HMAC must authorize'
);
$response = Bridge::handle_request( $request, 'seo-meta' );
expect_true( $response instanceof WP_REST_Response, 'valid read must return REST response' );
expect_true(
	$response->data['capability'] === 'rank-math/get-post-seo-meta',
	'capability identity mismatch'
);
expect_true( $response->data['wordpress_post_id'] === '5', 'post identity mismatch' );
expect_true(
	! array_key_exists( 'access_token', $response->data['safe_data'] ),
	'secret-shaped unknown field leaked'
);
expect_true(
	! array_key_exists( 'unknown_field', $response->data['safe_data'] ),
	'unknown field leaked'
);
expect_true(
	$response->data['rank_math_free_version'] === '1.0.279',
	'Rank Math version missing'
);
expect_true( $GLOBALS['bridge_current_user'] === 0, 'bridge user must be restored after request' );

$bad_request = new WP_REST_Request(
	'GET',
	$route,
	[
		'x-motgu-bridge-timestamp' => $timestamp,
		'x-motgu-bridge-signature' => str_repeat( '0', 64 ),
	],
	[ 'post_id' => '5' ]
);
expect_error_code(
	Bridge::authorize_request( $bad_request, 'seo-meta' ),
	'motgu_rank_math_bridge_unauthorized',
	'bad HMAC must fail closed'
);

$GLOBALS['bridge_abilities']['rank-math/get-post-schema'] = new FakeAbility(
	readonly_meta(),
	[
		'post_id'      => 5,
		'schema_types' => [ 'Article' ],
		'schemas'      => [
			[
				'@type'         => 'Article',
				'client_secret' => 'must-not-leak',
			],
		],
	]
);
$schema_route   = '/motgu-contentengine/v1/rank-math/posts/5/schema';
$schema_request = new WP_REST_Request(
	'GET',
	$schema_route,
	[],
	[ 'post_id' => '5' ]
);
$schema_result = Bridge::handle_request( $schema_request, 'schema' );
expect_error_code(
	$schema_result,
	'motgu_rank_math_bridge_sensitive_payload_rejected',
	'nested secret-shaped schema field must fail closed'
);

$GLOBALS['bridge_abilities']['rank-math/get-post-schema'] = new FakeAbility(
	readonly_meta(),
	[
		'post_id'      => 5,
		'schema_types' => [ 'EducationalOccupationalCredential' ],
		'schemas'      => [
			[
				'@type'              => 'EducationalOccupationalCredential',
				'credentialCategory' => 'Degree',
			],
		],
	]
);
$safe_schema = Bridge::handle_request( $schema_request, 'schema' );
expect_true(
	$safe_schema instanceof WP_REST_Response,
	'legitimate Schema credentialCategory must not be rejected as a secret'
);
expect_true(
	$safe_schema->data['safe_data']['schemas'][0]['credentialCategory'] === 'Degree',
	'legitimate Schema field must be preserved'
);

$invalid = new WP_REST_Request(
	'GET',
	'/motgu-contentengine/v1/rank-math/posts/0/seo-meta',
	[],
	[ 'post_id' => '0' ]
);
expect_error_code(
	Bridge::handle_request( $invalid, 'seo-meta' ),
	'motgu_rank_math_bridge_post_id_invalid',
	'invalid post id must fail closed'
);

fwrite( STDOUT, "PASS_P2C21_BRIDGE_CONTRACT\n" );