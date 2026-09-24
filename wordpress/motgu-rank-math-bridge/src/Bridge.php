<?php
/**
 * Read-only Rank Math bridge for ContentEngine.
 */

namespace MOTGU\ContentEngine\RankMathBridge;

use WP_Error;
use WP_REST_Request;
use WP_REST_Response;
use WP_REST_Server;

defined( 'ABSPATH' ) || exit;

final class Bridge {
	private const REST_NAMESPACE = 'motgu-contentengine/v1';
	private const PAYLOAD_SCHEMA_VERSION = '1';
	private const MAX_CLOCK_SKEW_SECONDS = 300;
	private const MAX_SAFE_DATA_BYTES = 524288;
	private const MAX_LINK_ITEMS = 1000;
	private const MAX_SCHEMA_DEPTH = 12;

	private const ROUTES = [
		'seo-meta' => [
			'ability'    => 'rank-math/get-post-seo-meta',
			'capability' => 'rank_math_onpage_general',
		],
		'schema' => [
			'ability'    => 'rank-math/get-post-schema',
			'capability' => 'rank_math_onpage_snippet',
		],
		'links' => [
			'ability'    => 'rank-math/get-post-links',
			'capability' => 'rank_math_link_builder',
		],
	];

	/**
	 * Register hooks. This plugin has no activation hook and writes no settings.
	 */
	public static function bootstrap(): void {
		add_action( 'rest_api_init', [ self::class, 'register_routes' ] );
	}

	/**
	 * Register three fixed GET routes. No arbitrary ability name is accepted.
	 */
	public static function register_routes(): void {
		foreach ( array_keys( self::ROUTES ) as $route_key ) {
			register_rest_route(
				self::REST_NAMESPACE,
				'/rank-math/posts/(?P<post_id>[1-9][0-9]*)/' . $route_key,
				[
					'methods'             => WP_REST_Server::READABLE,
					'callback'            => static function ( WP_REST_Request $request ) use ( $route_key ) {
						return self::handle_request( $request, $route_key );
					},
					'permission_callback' => static function ( WP_REST_Request $request ) use ( $route_key ) {
						return self::authorize_request( $request, $route_key );
					},
					'args'                => [
						'post_id' => [
							'required'          => true,
							'validate_callback' => static function ( $value ): bool {
								return is_scalar( $value ) && 1 === preg_match( '/\A[1-9][0-9]*\z/', (string) $value );
							},
						],
					],
				]
			);
		}
	}

	/**
	 * Authenticate one bridge request with a short-lived HMAC signature.
	 *
	 * Required wp-config.php constants (deployment only; never committed):
	 * MOTGU_RANK_MATH_BRIDGE_SECRET and MOTGU_RANK_MATH_BRIDGE_USER_ID.
	 *
	 * @return true|WP_Error
	 */
	public static function authorize_request( WP_REST_Request $request, string $route_key ) {
		if ( ! isset( self::ROUTES[ $route_key ] ) ) {
			return self::error( 'capability_forbidden', 403 );
		}

		$config_error = self::configuration_error();
		if ( $config_error instanceof WP_Error ) {
			return $config_error;
		}

		$timestamp = trim( (string) $request->get_header( 'x-motgu-bridge-timestamp' ) );
		$signature = strtolower( trim( (string) $request->get_header( 'x-motgu-bridge-signature' ) ) );
		if ( 1 !== preg_match( '/\A[0-9]{10,13}\z/', $timestamp ) || 1 !== preg_match( '/\A[a-f0-9]{64}\z/', $signature ) ) {
			return self::error( 'unauthorized', 401 );
		}

		$timestamp_int = (int) $timestamp;
		if ( abs( time() - $timestamp_int ) > self::MAX_CLOCK_SKEW_SECONDS ) {
			return self::error( 'signature_expired', 401 );
		}

		$expected = hash_hmac(
			'sha256',
			self::signature_message( $request, $timestamp ),
			(string) constant( 'MOTGU_RANK_MATH_BRIDGE_SECRET' )
		);

		if ( ! hash_equals( $expected, $signature ) ) {
			return self::error( 'unauthorized', 401 );
		}

		return true;
	}

	/**
	 * Execute one fixed read-only inspection route.
	 *
	 * @return WP_REST_Response|WP_Error
	 */
	public static function handle_request( WP_REST_Request $request, string $route_key ) {
		if ( ! isset( self::ROUTES[ $route_key ] ) ) {
			return self::error( 'capability_forbidden', 403 );
		}

		$post_id_raw = $request->get_param( 'post_id' );
		if ( ! is_scalar( $post_id_raw ) || 1 !== preg_match( '/\A[1-9][0-9]*\z/', (string) $post_id_raw ) ) {
			return self::error( 'post_id_invalid', 400 );
		}
		$post_id = (int) $post_id_raw;
		$post    = get_post( $post_id );
		if ( ! $post ) {
			return self::error( 'post_not_found', 404 );
		}

		$user_id = self::bridge_user_id();
		if ( $user_id <= 0 || ! get_user_by( 'id', $user_id ) ) {
			return self::error( 'service_user_invalid', 503 );
		}

		$route         = self::ROUTES[ $route_key ];
		$prior_user_id = get_current_user_id();
		wp_set_current_user( $user_id );
		try {
			if ( ! current_user_can( 'edit_post', $post_id ) || ! current_user_can( $route['capability'] ) ) {
				return self::error( 'forbidden', 403 );
			}

			$input = [ 'post_id' => $post_id ];
			if ( 'schema' === $route_key ) {
				$input['include_available_types'] = false;
			}

			$result = self::execute_allowed_ability( $route['ability'], $input );
		} finally {
			wp_set_current_user( $prior_user_id );
		}

		if ( $result instanceof WP_Error ) {
			return $result;
		}

		$safe_data = self::sanitize_result( $route_key, $post_id, $result );
		if ( $safe_data instanceof WP_Error ) {
			return $safe_data;
		}

		$encoded = wp_json_encode( $safe_data );
		if ( false === $encoded || strlen( $encoded ) > self::MAX_SAFE_DATA_BYTES ) {
			return self::error( 'payload_too_large', 502 );
		}

		$permalink = get_permalink( $post_id );
		$modified  = get_post_modified_time( 'Y-m-d\TH:i:s\Z', true, $post_id );
		$status    = get_post_status( $post_id );

		return rest_ensure_response(
			[
				'payload_schema_version' => self::PAYLOAD_SCHEMA_VERSION,
				'source'                 => 'rank_math',
				'upstream_source'        => 'rank_math_native',
				'capability'             => $route['ability'],
				'wordpress_post_id'      => (string) $post_id,
				'wordpress_url'          => is_string( $permalink ) ? $permalink : null,
				'wordpress_modified_gmt' => is_string( $modified ) ? $modified : null,
				'wordpress_status'       => is_string( $status ) ? $status : null,
				'rank_math_free_version' => defined( 'RANK_MATH_VERSION' ) ? (string) constant( 'RANK_MATH_VERSION' ) : null,
				'rank_math_pro_version'  => defined( 'RANK_MATH_PRO_VERSION' ) ? (string) constant( 'RANK_MATH_PRO_VERSION' ) : null,
				'captured_at'            => gmdate( 'c' ),
				'safe_data'              => $safe_data,
			]
		);
	}

	/**
	 * Execute only one of the compile-time allowlisted Rank Math read abilities.
	 *
	 * @param array<string,mixed> $input Ability input.
	 * @return array<string,mixed>|WP_Error
	 */
	public static function execute_allowed_ability( string $ability_name, array $input ) {
		$allowed = array_column( self::ROUTES, 'ability' );
		if ( ! in_array( $ability_name, $allowed, true ) ) {
			return self::error( 'capability_forbidden', 403 );
		}
		if ( ! function_exists( 'wp_get_ability' ) ) {
			return self::error( 'abilities_api_unavailable', 503 );
		}

		$ability = wp_get_ability( $ability_name );
		if ( ! is_object( $ability ) || ! method_exists( $ability, 'get_meta' ) || ! method_exists( $ability, 'execute' ) ) {
			return self::error( 'ability_unavailable', 503 );
		}

		$tracking_error = self::rank_math_tracking_error();
		if ( $tracking_error instanceof WP_Error ) {
			return $tracking_error;
		}

		$meta        = $ability->get_meta();
		$annotations = is_array( $meta ) && isset( $meta['annotations'] ) && is_array( $meta['annotations'] )
			? $meta['annotations']
			: [];
		if ( true !== ( $annotations['readonly'] ?? false ) || true === ( $annotations['destructive'] ?? false ) || true !== ( $annotations['idempotent'] ?? false ) ) {
			return self::error( 'ability_not_readonly', 503 );
		}

		$result = $ability->execute( $input );
		if ( $result instanceof WP_Error ) {
			$status = 'ability_invalid_permissions' === $result->get_error_code() ? 403 : 502;
			return self::error( 'ability_failed', $status, [ 'source_code' => $result->get_error_code() ] );
		}
		if ( ! is_array( $result ) || isset( $result['error'] ) ) {
			return self::error( 'ability_payload_invalid', 502 );
		}

		return $result;
	}

	/**
	 * Message shape used by the future ContentEngine gateway for HMAC signing.
	 */
	public static function signature_message( WP_REST_Request $request, string $timestamp ): string {
		return strtoupper( $request->get_method() ) . "\n" . $request->get_route() . "\n" . $timestamp;
	}

	/**
	 * @return true|WP_Error
	 */
	private static function configuration_error() {
		if ( ! defined( 'MOTGU_RANK_MATH_BRIDGE_SECRET' ) ) {
			return self::error( 'not_configured', 503 );
		}
		$secret = (string) constant( 'MOTGU_RANK_MATH_BRIDGE_SECRET' );
		if ( strlen( $secret ) < 32 ) {
			return self::error( 'not_configured', 503 );
		}
		if ( self::bridge_user_id() <= 0 ) {
			return self::error( 'not_configured', 503 );
		}
		return true;
	}

	private static function bridge_user_id(): int {
		if ( ! defined( 'MOTGU_RANK_MATH_BRIDGE_USER_ID' ) ) {
			return 0;
		}
		return (int) constant( 'MOTGU_RANK_MATH_BRIDGE_USER_ID' );
	}

	/**
	 * @param array<string,mixed> $result
	 * @return array<string,mixed>|WP_Error
	 */
	private static function sanitize_result( string $route_key, int $post_id, array $result ) {
		if ( ! isset( $result['post_id'] ) || (int) $result['post_id'] !== $post_id ) {
			return self::error( 'ability_identity_mismatch', 502 );
		}

		if ( 'seo-meta' === $route_key ) {
			return self::sanitize_seo_meta( $result );
		}
		if ( 'schema' === $route_key ) {
			return self::sanitize_schema( $result );
		}
		if ( 'links' === $route_key ) {
			return self::sanitize_links( $result );
		}
		return self::error( 'capability_forbidden', 403 );
	}

	/**
	 * @param array<string,mixed> $result
	 * @return array<string,mixed>|WP_Error
	 */
	private static function sanitize_seo_meta( array $result ) {
		$string_keys = [
			'title',
			'description',
			'focus_keyword',
			'canonical',
			'og_title',
			'og_description',
			'twitter_title',
			'twitter_description',
		];
		$safe = [ 'post_id' => (int) $result['post_id'] ];
		foreach ( $string_keys as $key ) {
			if ( array_key_exists( $key, $result ) ) {
				if ( ! is_string( $result[ $key ] ) ) {
					return self::error( 'ability_payload_invalid', 502 );
				}
				$safe[ $key ] = $result[ $key ];
			}
		}

		if ( array_key_exists( 'robots', $result ) ) {
			if ( ! is_array( $result['robots'] ) ) {
				return self::error( 'ability_payload_invalid', 502 );
			}
			$robots = [];
			foreach ( $result['robots'] as $robot ) {
				if ( ! is_string( $robot ) ) {
					return self::error( 'ability_payload_invalid', 502 );
				}
				$robots[] = $robot;
			}
			$safe['robots'] = $robots;
		}

		if ( array_key_exists( 'seo_score', $result ) ) {
			if ( ! is_int( $result['seo_score'] ) || $result['seo_score'] < 0 || $result['seo_score'] > 100 ) {
				return self::error( 'ability_payload_invalid', 502 );
			}
			$safe['seo_score'] = $result['seo_score'];
		}

		return $safe;
	}

	/**
	 * @param array<string,mixed> $result
	 * @return array<string,mixed>|WP_Error
	 */
	private static function sanitize_schema( array $result ) {
		if ( ! isset( $result['schema_types'], $result['schemas'] ) || ! is_array( $result['schema_types'] ) || ! is_array( $result['schemas'] ) ) {
			return self::error( 'ability_payload_invalid', 502 );
		}

		$types = [];
		foreach ( $result['schema_types'] as $type ) {
			if ( ! is_string( $type ) ) {
				return self::error( 'ability_payload_invalid', 502 );
			}
			$types[] = $type;
		}

		$schemas = [];
		foreach ( $result['schemas'] as $schema ) {
			$clean = self::sanitize_json_value( $schema, 0 );
			if ( $clean instanceof WP_Error ) {
				return $clean;
			}
			$schemas[] = $clean;
		}

		return [
			'post_id'      => (int) $result['post_id'],
			'schema_types' => $types,
			'schemas'      => $schemas,
		];
	}

	/**
	 * @param array<string,mixed> $result
	 * @return array<string,mixed>|WP_Error
	 */
	private static function sanitize_links( array $result ) {
		if ( ! isset( $result['internal'], $result['external'] ) || ! is_array( $result['internal'] ) || ! is_array( $result['external'] ) ) {
			return self::error( 'ability_payload_invalid', 502 );
		}
		if ( count( $result['internal'] ) + count( $result['external'] ) > self::MAX_LINK_ITEMS ) {
			return self::error( 'payload_too_large', 502 );
		}

		$internal = self::sanitize_link_items( $result['internal'], true );
		if ( $internal instanceof WP_Error ) {
			return $internal;
		}
		$external = self::sanitize_link_items( $result['external'], false );
		if ( $external instanceof WP_Error ) {
			return $external;
		}

		return [
			'post_id'  => (int) $result['post_id'],
			'internal' => $internal,
			'external' => $external,
			'counts'   => [
				'internal' => count( $internal ),
				'external' => count( $external ),
			],
		];
	}

	/**
	 * @param array<int,mixed> $items
	 * @return array<int,array<string,mixed>>|WP_Error
	 */
	private static function sanitize_link_items( array $items, bool $internal ) {
		$safe = [];
		foreach ( $items as $item ) {
			if ( ! is_array( $item ) || ! isset( $item['url'] ) || ! is_string( $item['url'] ) ) {
				return self::error( 'ability_payload_invalid', 502 );
			}
			if ( array_key_exists( 'anchor', $item ) && ! is_string( $item['anchor'] ) && null !== $item['anchor'] ) {
				return self::error( 'ability_payload_invalid', 502 );
			}
			if ( array_key_exists( 'dofollow', $item ) && ! is_bool( $item['dofollow'] ) && null !== $item['dofollow'] ) {
				return self::error( 'ability_payload_invalid', 502 );
			}

			$row = [
				'url'      => $item['url'],
				'anchor'   => $item['anchor'] ?? null,
				'dofollow' => $item['dofollow'] ?? null,
			];
			if ( $internal ) {
				if ( ! isset( $item['target_post_id'] ) || ! is_int( $item['target_post_id'] ) || $item['target_post_id'] <= 0 ) {
					return self::error( 'ability_payload_invalid', 502 );
				}
				$row['target_post_id'] = $item['target_post_id'];
			}
			$safe[] = $row;
		}
		return $safe;
	}

	/**
	 * Validate an arbitrary schema object as bounded JSON while blocking secret-shaped keys.
	 *
	 * @return mixed|WP_Error
	 */
	private static function sanitize_json_value( $value, int $depth ) {
		if ( $depth > self::MAX_SCHEMA_DEPTH ) {
			return self::error( 'payload_too_deep', 502 );
		}
		if ( null === $value || is_string( $value ) || is_int( $value ) || is_float( $value ) || is_bool( $value ) ) {
			return $value;
		}
		if ( ! is_array( $value ) ) {
			return self::error( 'ability_payload_invalid', 502 );
		}

		$clean = [];
		foreach ( $value as $key => $item ) {
			if ( is_string( $key ) && self::is_sensitive_key( $key ) ) {
				return self::error( 'sensitive_payload_rejected', 502 );
			}
			$child = self::sanitize_json_value( $item, $depth + 1 );
			if ( $child instanceof WP_Error ) {
				return $child;
			}
			$clean[ $key ] = $child;
		}
		return $clean;
	}

	/**
	 * Rank Math read abilities emit usage telemetry when its usage tracking is opted in.
	 * Refuse execution instead of silently turning a read inspection into a third-party
	 * network side effect. The bridge never changes that preference.
	 *
	 * @return true|WP_Error
	 */
	private static function rank_math_tracking_error() {
		if ( ! function_exists( 'rank_math' ) ) {
			return self::error( 'rank_math_runtime_unavailable', 503 );
		}

		$rank_math = rank_math();
		if ( ! is_object( $rank_math ) || ! isset( $rank_math->tracking ) || ! is_object( $rank_math->tracking ) || ! method_exists( $rank_math->tracking, 'is_opted_in' ) ) {
			return self::error( 'rank_math_tracking_state_unknown', 503 );
		}
		if ( true === $rank_math->tracking->is_opted_in() ) {
			return self::error( 'rank_math_tracking_enabled', 503 );
		}

		return true;
	}

	/**
	 * Reject exact secret-bearing field names without blocking legitimate Schema.org
	 * fields such as credentialCategory.
	 */
	private static function is_sensitive_key( string $key ): bool {
		$normalized = strtolower( str_replace( '-', '_', trim( $key ) ) );
		return in_array(
			$normalized,
			[
				'access_token',
				'refresh_token',
				'auth_token',
				'id_token',
				'api_key',
				'apikey',
				'client_secret',
				'private_key',
				'secret',
				'password',
				'authorization',
				'cookie',
				'credential',
				'credentials',
			],
			true
		);
	}

	/**
	 * Build a stable public error without leaking upstream payloads or credentials.
	 *
	 * @param array<string,mixed> $extra
	 */
	private static function error( string $suffix, int $status, array $extra = [] ): WP_Error {
		return new WP_Error(
			'motgu_rank_math_bridge_' . $suffix,
			'Rank Math bridge request failed.',
			array_merge( [ 'status' => $status ], $extra )
		);
	}
}